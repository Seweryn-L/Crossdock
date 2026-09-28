"""Map a raw spreadsheet row dict into domain models (pydantic boundary)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import ValidationError

from crossdock.domain.models import Location, Order, Shipment
from crossdock.excel_mapping import ExcelColumnMapping

LB_TO_KG = 0.45359237


def _cell(row: dict[str, Any], mapping: ExcelColumnMapping, logical: str) -> Any:
    col = mapping.column(logical)
    if col not in row:
        return None
    value = row[col]
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        if value.is_integer():
            return str(int(value))
        return str(value).strip() or None
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    return text or None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Multi-SKU Product Weight: "12.3,45.6" (comma separates; dot is decimal).
    if "," in text and "." in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) > 1:
            return sum(float(p) for p in parts)
    return float(text.replace(",", "."))


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _parse_date(value: Any, formats: list[str]) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    # Excel sometimes yields timestamps as "YYYY-MM-DD HH:MM:SS"
    text = text.split()[0]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"nieznany format daty: {text!r}")


def _weight_kg(value: Any, unit: str) -> float | None:
    raw = _as_float(value)
    if raw is None:
        return None
    if unit == "lb":
        return raw * LB_TO_KG
    return raw


def _split_id_list(value: Any) -> list[str]:
    """Split comma-separated reference / TMS IDs from one spreadsheet cell."""
    text = _as_str(value)
    if not text:
        return []
    if "," not in text:
        return [text]
    return [part.strip() for part in text.split(",") if part.strip()]


def _weight_parts_kg(value: Any, unit: str) -> list[float]:
    """Parse one or more weights from a cell (comma-separated SKU weights)."""
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    if "," in text:
        parts: list[float] = []
        for piece in text.split(","):
            piece = piece.strip()
            if not piece:
                continue
            raw = _as_float(piece)
            if raw is None:
                continue
            converted = raw * LB_TO_KG if unit == "lb" else raw
            parts.append(converted)
        return parts
    single = _weight_kg(value, unit)
    return [single] if single is not None else []


def _pick_weight(weights: list[float], index: int, count: int) -> float | None:
    if not weights:
        return None
    if len(weights) == count:
        return weights[index]
    if len(weights) == 1:
        return weights[0]
    if index < len(weights):
        return weights[index]
    return weights[-1]


def _build_shipments(
    delivery_refs: list[str],
    shipment_ids: list[str],
    weights: list[float],
    *,
    pallet_count: int | None,
) -> list[Shipment]:
    """Expand one spreadsheet row into one or more domain shipments."""
    if len(delivery_refs) > 1:
        count = len(delivery_refs)
        out: list[Shipment] = []
        for i, ref in enumerate(delivery_refs):
            if len(shipment_ids) == count:
                shipment_number = shipment_ids[i]
            elif len(shipment_ids) == 1:
                shipment_number = ref
            elif len(shipment_ids) > i:
                shipment_number = shipment_ids[i]
            elif shipment_ids:
                shipment_number = f"{shipment_ids[0]}-{i + 1}"
            else:
                shipment_number = ref
            out.append(
                Shipment(
                    shipment_number=shipment_number,
                    pallet_count=pallet_count,
                    weight_kg=_pick_weight(weights, i, count),
                )
            )
        return out

    if len(shipment_ids) > 1:
        count = len(shipment_ids)
        return [
            Shipment(
                shipment_number=shipment_ids[i],
                pallet_count=pallet_count,
                weight_kg=_pick_weight(weights, i, count),
            )
            for i in range(count)
        ]

    shipment_number = shipment_ids[0] if shipment_ids else delivery_refs[0]
    total_weight = sum(weights) if weights else None
    return [
        Shipment(
            shipment_number=shipment_number,
            pallet_count=pallet_count,
            weight_kg=total_weight,
        )
    ]


def row_to_shipment_and_locations(
    row: dict[str, Any],
    mapping: ExcelColumnMapping,
    *,
    default_delivery_days: int,
    ship_lead_days: int = 2,
    as_of: date | None = None,
) -> Order:
    """Build a single-shipment Order from one spreadsheet row.

    Caller groups rows by delivery_code into multi-shipment orders.
    """
    delivery_code_raw = _cell(row, mapping, "delivery_code")
    shipment_number_raw = _cell(row, mapping, "shipment_number")
    delivery_refs = _split_id_list(delivery_code_raw)
    shipment_ids = _split_id_list(shipment_number_raw)
    if not delivery_refs:
        raise ValueError("brak kodu dostawy (delivery_code)")
    if not shipment_ids and len(delivery_refs) == 1:
        raise ValueError("brak numeru przesyłki (shipment_number)")
    delivery_code = _as_str(delivery_code_raw) or delivery_refs[0]

    pickup_name = _as_str(_cell(row, mapping, "pickup_name"))
    delivery_name = _as_str(_cell(row, mapping, "delivery_name"))
    if not pickup_name:
        raise ValueError("brak miejsca odbioru (pickup_name)")
    if not delivery_name:
        raise ValueError("brak miejsca dostawy (delivery_name)")

    # Pallet count is often missing. Keep None, do not invent a number.
    pallet_count = None
    if "pallet_count" in mapping.columns:
        try:
            pallet_count = _as_int(_cell(row, mapping, "pallet_count"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"niepoprawna liczba palet: {exc}") from exc

    try:
        weight_parts = _weight_parts_kg(_cell(row, mapping, "weight_kg"), mapping.weight_unit)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"niepoprawna waga: {exc}") from exc

    shipments = _build_shipments(
        delivery_refs,
        shipment_ids,
        weight_parts,
        pallet_count=pallet_count,
    )

    try:
        delivery_date = _parse_date(_cell(row, mapping, "delivery_date"), mapping.date_formats)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    must_leave_by: date | None = None
    if "must_leave_by" in mapping.columns:
        try:
            must_leave_by = _parse_date(_cell(row, mapping, "must_leave_by"), mapping.date_formats)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    try:
        return Order.create(
            delivery_code=delivery_code,
            shipments=shipments,
            pickup_location=Location(
                name=pickup_name,
                city=_as_str(_cell(row, mapping, "pickup_city")),
                country=_as_str(_cell(row, mapping, "pickup_country")),
                postal_code=_as_str(_cell(row, mapping, "pickup_postal_code")),
            ),
            delivery_location=Location(
                name=delivery_name,
                city=_as_str(_cell(row, mapping, "delivery_city")),
                country=_as_str(_cell(row, mapping, "delivery_country")),
                postal_code=_as_str(_cell(row, mapping, "delivery_postal_code")),
            ),
            delivery_date=delivery_date,
            must_leave_by=must_leave_by,
            default_delivery_days=default_delivery_days,
            ship_lead_days=ship_lead_days,
            as_of=as_of,
        )
    except ValidationError as exc:
        raise ValueError(f"walidacja domenowa: {exc.errors()[0]['msg']}") from exc
