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


def row_to_shipment_and_locations(
    row: dict[str, Any],
    mapping: ExcelColumnMapping,
    *,
    default_delivery_days: int,
) -> Order:
    """Build a single-shipment Order from one spreadsheet row.

    Caller groups rows by delivery_code into multi-shipment orders.
    """
    delivery_code = _as_str(_cell(row, mapping, "delivery_code"))
    shipment_number = _as_str(_cell(row, mapping, "shipment_number"))
    if not delivery_code:
        raise ValueError("brak kodu dostawy (delivery_code)")
    if not shipment_number:
        raise ValueError("brak numeru przesyłki (shipment_number)")

    pickup_name = _as_str(_cell(row, mapping, "pickup_name"))
    delivery_name = _as_str(_cell(row, mapping, "delivery_name"))
    if not pickup_name:
        raise ValueError("brak miejsca odbioru (pickup_name)")
    if not delivery_name:
        raise ValueError("brak miejsca dostawy (delivery_name)")

    # Excel has no pallet column today; hook stays for a future column (overrides estimate).
    pallet_count = None
    if "pallet_count" in mapping.columns:
        try:
            pallet_count = _as_int(_cell(row, mapping, "pallet_count"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"niepoprawna liczba palet: {exc}") from exc

    try:
        weight_kg = _weight_kg(_cell(row, mapping, "weight_kg"), mapping.weight_unit)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"niepoprawna waga: {exc}") from exc

    try:
        delivery_date = _parse_date(_cell(row, mapping, "delivery_date"), mapping.date_formats)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        return Order.create(
            delivery_code=delivery_code,
            shipments=[
                Shipment(
                    shipment_number=shipment_number,
                    pallet_count=pallet_count,
                    weight_kg=weight_kg,
                )
            ],
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
            default_delivery_days=default_delivery_days,
        )
    except ValidationError as exc:
        raise ValueError(f"walidacja domenowa: {exc.errors()[0]['msg']}") from exc
