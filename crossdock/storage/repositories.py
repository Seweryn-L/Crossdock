"""Repositories — the only place that touches ORM sessions directly."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from crossdock.domain.models import (
    Location,
    Order,
    OrderStatus,
    Role,
    Shipment,
    User,
    Vehicle,
    VehicleType,
)
from crossdock.storage.tables import (
    AssignmentItemRow,
    AssignmentRouteRow,
    AssignmentRunRow,
    AuditLogRow,
    LocationCoordsRow,
    OrderRow,
    ShipmentRow,
    UserRow,
    VehicleRow,
    WarehouseQueueRow,
)


def _to_domain_user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        role=Role(row.role),
        is_active=row.is_active,
    )


def _to_domain_vehicle(row: VehicleRow) -> Vehicle:
    return Vehicle(
        id=row.id,
        code=row.code,
        vehicle_type=VehicleType(row.vehicle_type),
        pallet_capacity=row.pallet_capacity,
        weight_capacity_kg=row.weight_capacity_kg,
        is_active=row.is_active,
        is_placeholder=row.is_placeholder,
        is_busy=bool(row.is_busy),
    )


def _to_domain_order(row: OrderRow) -> Order:
    return Order(
        id=row.id,
        delivery_code=row.delivery_code,
        shipments=[
            Shipment(
                shipment_number=s.shipment_number,
                pallet_count=s.pallet_count,
                weight_kg=s.weight_kg,
            )
            for s in row.shipments
        ],
        pickup_location=Location(
            name=row.pickup_name,
            city=row.pickup_city,
            country=row.pickup_country,
            postal_code=row.pickup_postal_code,
            latitude=row.pickup_latitude,
            longitude=row.pickup_longitude,
        ),
        delivery_location=Location(
            name=row.delivery_name,
            city=row.delivery_city,
            country=row.delivery_country,
            postal_code=row.delivery_postal_code,
            latitude=row.delivery_latitude,
            longitude=row.delivery_longitude,
        ),
        delivery_date=row.delivery_date,
        status=OrderStatus(row.status),
    )


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        row = self._get_row(username)
        return _to_domain_user(row) if row else None

    def get_password_hash(self, username: str) -> str | None:
        row = self._get_row(username)
        return row.password_hash if row else None

    def add(self, username: str, password_hash: str, role: Role) -> User:
        row = UserRow(username=username, password_hash=password_hash, role=role.value)
        self._session.add(row)
        self._session.flush()
        return _to_domain_user(row)

    def update_password_hash(self, username: str, password_hash: str) -> None:
        row = self._get_row(username)
        if row is not None:
            row.password_hash = password_hash

    def list_all(self) -> list[User]:
        rows = self._session.scalars(select(UserRow).order_by(UserRow.username)).all()
        return [_to_domain_user(r) for r in rows]

    def count(self) -> int:
        return len(self._session.scalars(select(UserRow.id)).all())

    def _get_row(self, username: str) -> UserRow | None:
        return self._session.scalar(select(UserRow).where(UserRow.username == username))


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, username: str, action: str, details: dict[str, Any] | None = None) -> None:
        self._session.add(
            AuditLogRow(
                username=username,
                action=action,
                details=json.dumps(details, ensure_ascii=False) if details else None,
            )
        )


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_many(self, orders: list[Order]) -> list[Order]:
        saved: list[Order] = []
        for order in orders:
            row = OrderRow(
                delivery_code=order.delivery_code,
                pickup_name=order.pickup_location.name,
                pickup_city=order.pickup_location.city,
                pickup_country=order.pickup_location.country,
                pickup_postal_code=order.pickup_location.postal_code,
                pickup_latitude=order.pickup_location.latitude,
                pickup_longitude=order.pickup_location.longitude,
                delivery_name=order.delivery_location.name,
                delivery_city=order.delivery_location.city,
                delivery_country=order.delivery_location.country,
                delivery_postal_code=order.delivery_location.postal_code,
                delivery_latitude=order.delivery_location.latitude,
                delivery_longitude=order.delivery_location.longitude,
                delivery_date=order.delivery_date,
                status=order.status.value,
                shipments=[
                    ShipmentRow(
                        shipment_number=s.shipment_number,
                        pallet_count=s.pallet_count,
                        weight_kg=s.weight_kg,
                    )
                    for s in order.shipments
                ],
            )
            self._session.add(row)
            self._session.flush()
            saved.append(_to_domain_order(row))
        return saved

    def list_all(self) -> list[Order]:
        stmt = (
            select(OrderRow)
            .options(selectinload(OrderRow.shipments))
            .order_by(OrderRow.delivery_date, OrderRow.delivery_code)
        )
        return [_to_domain_order(r) for r in self._session.scalars(stmt).all()]

    def list_filtered(
        self,
        *,
        statuses: list[OrderStatus] | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        exclude_statuses: list[OrderStatus] | None = None,
    ) -> list[Order]:
        """List orders with optional status and delivery_date range filters."""
        stmt = select(OrderRow).options(selectinload(OrderRow.shipments))
        if statuses:
            stmt = stmt.where(OrderRow.status.in_([s.value for s in statuses]))
        if exclude_statuses:
            stmt = stmt.where(OrderRow.status.notin_([s.value for s in exclude_statuses]))
        if due_from is not None:
            stmt = stmt.where(OrderRow.delivery_date >= due_from)
        if due_to is not None:
            stmt = stmt.where(OrderRow.delivery_date <= due_to)
        stmt = stmt.order_by(OrderRow.delivery_date, OrderRow.delivery_code)
        return [_to_domain_order(r) for r in self._session.scalars(stmt).all()]

    def list_active_delivery_codes(self) -> set[str]:
        """Delivery codes for orders that are not yet delivered (ops pool)."""
        rows = self._session.execute(
            select(OrderRow.delivery_code).where(OrderRow.status != OrderStatus.DELIVERED.value)
        ).all()
        return {str(code) for (code,) in rows}

    def list_by_status(self, status: OrderStatus) -> list[Order]:
        stmt = (
            select(OrderRow)
            .options(selectinload(OrderRow.shipments))
            .where(OrderRow.status == status.value)
            .order_by(OrderRow.delivery_date, OrderRow.delivery_code)
        )
        return [_to_domain_order(r) for r in self._session.scalars(stmt).all()]

    def count(self) -> int:
        return len(self._session.scalars(select(OrderRow.id)).all())

    def existing_delivery_code_ids(self, codes: list[str]) -> dict[str, int]:
        """Map delivery_code → first matching order id (cheap duplicate lookup)."""
        if not codes:
            return {}
        rows = self._session.execute(
            select(OrderRow.delivery_code, OrderRow.id).where(OrderRow.delivery_code.in_(codes))
        ).all()
        result: dict[str, int] = {}
        for code, order_id in rows:
            if code not in result:
                result[code] = int(order_id)
        return result

    def existing_delivery_codes(self, codes: list[str]) -> set[str]:
        return set(self.existing_delivery_code_ids(codes))

    def get_by_id(self, order_id: int) -> Order | None:
        row = self._session.scalar(
            select(OrderRow)
            .options(selectinload(OrderRow.shipments))
            .where(OrderRow.id == order_id)
        )
        return _to_domain_order(row) if row else None

    def delete_by_ids(self, order_ids: list[int]) -> int:
        if not order_ids:
            return 0
        rows = self._session.scalars(select(OrderRow).where(OrderRow.id.in_(order_ids))).all()
        for row in rows:
            self._session.delete(row)
        self._session.flush()
        return len(rows)

    def delete_all(self) -> int:
        rows = self._session.scalars(select(OrderRow)).all()
        count = len(rows)
        for row in rows:
            self._session.delete(row)
        self._session.flush()
        return count

    def count_by_status(self, status: OrderStatus) -> int:
        return len(
            self._session.scalars(select(OrderRow.id).where(OrderRow.status == status.value)).all()
        )

    def set_status_many(self, order_ids: list[int], status: OrderStatus) -> int:
        if not order_ids:
            return 0
        rows = self._session.scalars(select(OrderRow).where(OrderRow.id.in_(order_ids))).all()
        for row in rows:
            row.status = status.value
        self._session.flush()
        return len(rows)

    def update_order_pallets(self, order_id: int, total_pallets: int) -> Order:
        """Set order total pallets on first shipment; others → 0 (FR-021 MVP)."""
        if total_pallets < 0:
            raise ValueError("Liczba palet nie może być ujemna.")
        row = self._session.scalar(
            select(OrderRow)
            .options(selectinload(OrderRow.shipments))
            .where(OrderRow.id == order_id)
        )
        if row is None:
            raise ValueError(f"Zlecenie #{order_id} nie istnieje.")
        if not row.shipments:
            raise ValueError(f"Zlecenie #{order_id} nie ma przesyłek.")
        for idx, shipment in enumerate(row.shipments):
            shipment.pallet_count = total_pallets if idx == 0 else 0
        self._session.flush()
        return _to_domain_order(row)


class VehicleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Vehicle]:
        rows = self._session.scalars(select(VehicleRow).order_by(VehicleRow.code)).all()
        return [_to_domain_vehicle(r) for r in rows]

    def list_active(self) -> list[Vehicle]:
        rows = self._session.scalars(
            select(VehicleRow).where(VehicleRow.is_active.is_(True)).order_by(VehicleRow.code)
        ).all()
        return [_to_domain_vehicle(r) for r in rows]

    def list_available(self) -> list[Vehicle]:
        rows = self._session.scalars(
            select(VehicleRow)
            .where(VehicleRow.is_active.is_(True), VehicleRow.is_busy.is_(False))
            .order_by(VehicleRow.code)
        ).all()
        return [_to_domain_vehicle(r) for r in rows]

    def list_by_type(self, vehicle_type: VehicleType) -> list[Vehicle]:
        rows = self._session.scalars(
            select(VehicleRow)
            .where(VehicleRow.vehicle_type == vehicle_type.value)
            .order_by(VehicleRow.code)
        ).all()
        return [_to_domain_vehicle(r) for r in rows]

    def count(self) -> int:
        return len(self._session.scalars(select(VehicleRow.id)).all())

    def get(self, vehicle_id: int) -> Vehicle | None:
        row = self._session.get(VehicleRow, vehicle_id)
        return _to_domain_vehicle(row) if row else None

    def get_by_code(self, code: str) -> Vehicle | None:
        row = self._session.scalar(select(VehicleRow).where(VehicleRow.code == code))
        return _to_domain_vehicle(row) if row else None

    def add(self, vehicle: Vehicle) -> Vehicle:
        row = VehicleRow(
            code=vehicle.code,
            vehicle_type=vehicle.vehicle_type.value,
            pallet_capacity=vehicle.pallet_capacity,
            weight_capacity_kg=vehicle.weight_capacity_kg,
            is_active=vehicle.is_active,
            is_placeholder=vehicle.is_placeholder,
            is_busy=vehicle.is_busy,
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain_vehicle(row)

    def set_busy(self, vehicle_id: int, busy: bool) -> Vehicle | None:
        row = self._session.get(VehicleRow, vehicle_id)
        if row is None:
            return None
        row.is_busy = busy
        self._session.flush()
        return _to_domain_vehicle(row)

    def update(self, vehicle: Vehicle) -> Vehicle | None:
        if vehicle.id is None:
            return None
        row = self._session.get(VehicleRow, vehicle.id)
        if row is None:
            return None
        row.code = vehicle.code
        row.vehicle_type = vehicle.vehicle_type.value
        row.pallet_capacity = vehicle.pallet_capacity
        row.weight_capacity_kg = vehicle.weight_capacity_kg
        row.is_active = vehicle.is_active
        row.is_placeholder = vehicle.is_placeholder
        self._session.flush()
        return _to_domain_vehicle(row)


class LocationCoordsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, location_key: str) -> Location | None:
        row = self._session.scalar(
            select(LocationCoordsRow).where(LocationCoordsRow.location_key == location_key)
        )
        if row is None:
            return None
        return Location(
            name=row.name,
            city=row.city,
            country=row.country,
            postal_code=row.postal_code,
            latitude=row.latitude,
            longitude=row.longitude,
        )

    def upsert(self, location: Location) -> Location:
        key = location.location_key()
        if location.latitude is None or location.longitude is None:
            raise ValueError("latitude and longitude are required for coordinate dictionary")
        row = self._session.scalar(
            select(LocationCoordsRow).where(LocationCoordsRow.location_key == key)
        )
        if row is None:
            row = LocationCoordsRow(
                location_key=key,
                name=location.name,
                city=location.city,
                country=location.country,
                postal_code=location.postal_code,
                latitude=location.latitude,
                longitude=location.longitude,
            )
            self._session.add(row)
        else:
            row.name = location.name
            row.city = location.city
            row.country = location.country
            row.postal_code = location.postal_code
            row.latitude = location.latitude
            row.longitude = location.longitude
        self._session.flush()
        return location

    def list_all(self) -> list[Location]:
        rows = self._session.scalars(
            select(LocationCoordsRow).order_by(LocationCoordsRow.name)
        ).all()
        return [
            Location(
                name=r.name,
                city=r.city,
                country=r.country,
                postal_code=r.postal_code,
                latitude=r.latitude,
                longitude=r.longitude,
            )
            for r in rows
        ]

    def count(self) -> int:
        return len(self._session.scalars(select(LocationCoordsRow.id)).all())

    def delete_by_key(self, location_key: str) -> bool:
        row = self._session.scalar(
            select(LocationCoordsRow).where(LocationCoordsRow.location_key == location_key)
        )
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def find_by_city_country(self, city: str | None, country: str | None) -> Location | None:
        """Fallback lookup when exact location_key is missing (city centroid)."""
        if not city:
            return None
        city_norm = city.strip().lower()
        country_norm = (country or "").strip().lower()
        rows = self._session.scalars(select(LocationCoordsRow)).all()
        for row in rows:
            if (row.city or "").strip().lower() != city_norm:
                continue
            if country_norm and (row.country or "").strip().lower() != country_norm:
                continue
            return Location(
                name=row.name,
                city=row.city,
                country=row.country,
                postal_code=row.postal_code,
                latitude=row.latitude,
                longitude=row.longitude,
            )
        return None


class AssignmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_run(
        self,
        *,
        username: str,
        status: str,
        wall_time_s: float,
        warnings: list[str],
        loads: list[dict[str, Any]],
        unassigned_order_ids: list[int],
        order_meta: dict[int, tuple[str, float]],
    ) -> int:
        """Persist assignment. ``loads`` items: vehicle_id, vehicle_code, order_ids, fill_ratio."""
        return self.save_plan_run(
            username=username,
            status=status,
            wall_time_s=wall_time_s,
            warnings=warnings,
            items=[],
            routes=[],
            unassigned_order_ids=unassigned_order_ids,
            order_meta=order_meta,
            loads=loads,
            total_distance_km=None,
            total_cost_eur=None,
        )

    def save_plan_run(
        self,
        *,
        username: str,
        status: str,
        wall_time_s: float,
        warnings: list[str],
        items: list[dict[str, Any]],
        routes: list[dict[str, Any]],
        unassigned_order_ids: list[int],
        order_meta: dict[int, tuple[str, float]],
        loads: list[dict[str, Any]] | None = None,
        total_distance_km: float | None = None,
        total_cost_eur: float | None = None,
        existing_run_id: int | None = None,
    ) -> int:
        """Persist a full plan (assignment items + routes).

        ``items`` entries: vehicle_id, vehicle_code, order_id, fill_ratio,
        sequence, drop_key.
        When ``items`` is empty and ``loads`` is provided, expand loads (T3 compat).
        When ``existing_run_id`` is set, append to that draft/partial run
        (approved routes must already have been kept).
        """
        if existing_run_id is not None:
            run = self.get_run(existing_run_id)
            if run is None:
                raise ValueError(f"Plan run #{existing_run_id} nie istnieje.")
            run.status = status
            run.wall_time_s = wall_time_s
            run.unassigned_count = len(unassigned_order_ids)
            run.warnings_json = json.dumps(warnings, ensure_ascii=False) if warnings else None
            if total_distance_km is not None:
                run.total_distance_km = total_distance_km
            if total_cost_eur is not None:
                run.total_cost_eur = total_cost_eur
            self._session.flush()
        else:
            run = AssignmentRunRow(
                username=username,
                status=status,
                wall_time_s=wall_time_s,
                unassigned_count=len(unassigned_order_ids),
                warnings_json=json.dumps(warnings, ensure_ascii=False) if warnings else None,
                plan_status="draft",
                total_distance_km=total_distance_km,
                total_cost_eur=total_cost_eur,
            )
            self._session.add(run)
            self._session.flush()

        expanded = list(items)
        if not expanded and loads:
            for load in loads:
                fill = load.get("fill_ratio")
                for order_id in load["order_ids"]:
                    expanded.append(
                        {
                            "vehicle_id": load.get("vehicle_id"),
                            "vehicle_code": load["vehicle_code"],
                            "order_id": int(order_id),
                            "fill_ratio": fill,
                            "sequence": None,
                            "drop_key": None,
                        }
                    )

        for item in expanded:
            order_id = int(item["order_id"])
            code, weight = order_meta.get(order_id, ("?", 0.0))
            self._session.add(
                AssignmentItemRow(
                    run_id=run.id,
                    vehicle_id=item.get("vehicle_id"),
                    vehicle_code=str(item["vehicle_code"]),
                    order_id=order_id,
                    delivery_code=code,
                    weight_kg=weight,
                    fill_ratio=item.get("fill_ratio"),
                    sequence=item.get("sequence"),
                    drop_key=item.get("drop_key"),
                )
            )
        for order_id in unassigned_order_ids:
            code, weight = order_meta.get(order_id, ("?", 0.0))
            self._session.add(
                AssignmentItemRow(
                    run_id=run.id,
                    vehicle_id=None,
                    vehicle_code="UNASSIGNED",
                    order_id=order_id,
                    delivery_code=code,
                    weight_kg=weight,
                    fill_ratio=None,
                    sequence=None,
                    drop_key=None,
                )
            )
        for route in routes:
            polyline = route.get("polyline")
            polyline_json: str | None = None
            if polyline is not None:
                polyline_json = json.dumps(list(polyline), ensure_ascii=False)
            elif route.get("polyline_json") is not None:
                polyline_json = str(route["polyline_json"])
            self._session.add(
                AssignmentRouteRow(
                    run_id=run.id,
                    vehicle_id=route.get("vehicle_id"),
                    vehicle_code=str(route["vehicle_code"]),
                    drop_count=int(route["drop_count"]),
                    distance_km=float(route["distance_km"]),
                    cost_eur=float(route["cost_eur"]),
                    route_status=str(route.get("route_status") or "proposed"),
                    polyline_json=polyline_json,
                )
            )
        self._session.flush()
        if existing_run_id is not None:
            self.refresh_run_totals(run.id)
        return run.id

    def delete_proposed_payload(self, run_id: int) -> None:
        """Drop proposed routes and non-approved items; keep approved routes."""
        routes = self.list_routes_for_run(run_id)
        approved_vehicle_ids = {
            r.vehicle_id
            for r in routes
            if r.route_status == "approved" and r.vehicle_id is not None
        }
        for item in self.list_items_for_run(run_id):
            keep_approved = item.vehicle_id in approved_vehicle_ids and item.vehicle_code not in {
                "UNASSIGNED",
                "UNROUTED",
            }
            if not keep_approved:
                self._session.delete(item)
        for route in routes:
            if route.route_status != "approved":
                self._session.delete(route)
        self._session.flush()

    def refresh_run_totals(self, run_id: int) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        routes = self.list_routes_for_run(run_id)
        run.total_distance_km = sum(r.distance_km for r in routes)
        run.total_cost_eur = sum(r.cost_eur for r in routes)
        items = self.list_items_for_run(run_id)
        run.unassigned_count = sum(1 for i in items if i.vehicle_code == "UNASSIGNED")
        self._session.flush()

    def get_latest_run_id(self) -> int | None:
        row = self._session.scalar(
            select(AssignmentRunRow).order_by(AssignmentRunRow.id.desc()).limit(1)
        )
        return row.id if row else None

    def get_run(self, run_id: int) -> AssignmentRunRow | None:
        return self._session.scalar(select(AssignmentRunRow).where(AssignmentRunRow.id == run_id))

    def get_latest_run(self) -> AssignmentRunRow | None:
        return self._session.scalar(
            select(AssignmentRunRow).order_by(AssignmentRunRow.id.desc()).limit(1)
        )

    def resolve_run_id(self, preferred: int | None) -> int | None:
        """Return preferred run if it exists, otherwise the latest run id."""
        if preferred is not None:
            run = self.get_run(preferred)
            if run is not None:
                return run.id
        latest = self.get_latest_run()
        return latest.id if latest else None

    def resolve_operational_run_id(self) -> int | None:
        """Latest generation — continuous ops default (no plan picker)."""
        latest = self.get_latest_run()
        return latest.id if latest else None

    def count_routes_by_status(self, run_id: int) -> dict[str, int]:
        counts = {"proposed": 0, "approved": 0, "completed": 0}
        for route in self.list_routes_for_run(run_id):
            status = route.route_status or "proposed"
            if status in counts:
                counts[status] += 1
            else:
                counts["proposed"] += 1
        return counts

    def list_recent_runs(self, *, limit: int = 30) -> list[AssignmentRunRow]:
        return list(
            self._session.scalars(
                select(AssignmentRunRow).order_by(AssignmentRunRow.id.desc()).limit(limit)
            ).all()
        )

    def set_display_name(self, run_id: int, display_name: str | None) -> AssignmentRunRow:
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        run.display_name = display_name
        self._session.flush()
        return run

    def get_latest_approved_run(self) -> AssignmentRunRow | None:
        return self._session.scalar(
            select(AssignmentRunRow)
            .where(AssignmentRunRow.plan_status == "approved")
            .order_by(AssignmentRunRow.id.desc())
            .limit(1)
        )

    def list_items_for_run(self, run_id: int) -> list[AssignmentItemRow]:
        return list(
            self._session.scalars(
                select(AssignmentItemRow)
                .where(AssignmentItemRow.run_id == run_id)
                .order_by(
                    AssignmentItemRow.vehicle_code,
                    AssignmentItemRow.sequence.nulls_last(),
                    AssignmentItemRow.delivery_code,
                )
            ).all()
        )

    def list_routes_for_run(self, run_id: int) -> list[AssignmentRouteRow]:
        return list(
            self._session.scalars(
                select(AssignmentRouteRow)
                .where(AssignmentRouteRow.run_id == run_id)
                .order_by(AssignmentRouteRow.vehicle_code)
            ).all()
        )

    def approve_run(self, run_id: int, *, username: str) -> AssignmentRunRow:
        from datetime import UTC, datetime

        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        if run.plan_status == "approved":
            raise ValueError(f"Plan run #{run_id} jest już zatwierdzony.")
        run.plan_status = "approved"
        run.approved_at = datetime.now(UTC).replace(tzinfo=None)
        run.approved_by = username
        self._session.flush()
        return run

    def set_run_status(self, run_id: int, *, plan_status: str) -> AssignmentRunRow:
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        run.plan_status = plan_status
        if plan_status != "approved":
            run.approved_at = None
            run.approved_by = None
        self._session.flush()
        return run

    def delete_run(self, run_id: int) -> None:
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        self._session.delete(run)
        self._session.flush()


class WarehouseQueueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_ordered(self) -> list[WarehouseQueueRow]:
        return list(
            self._session.scalars(
                select(WarehouseQueueRow).order_by(WarehouseQueueRow.position)
            ).all()
        )

    def get_by_order_id(self, order_id: int) -> WarehouseQueueRow | None:
        return self._session.scalar(
            select(WarehouseQueueRow).where(WarehouseQueueRow.order_id == order_id)
        )

    def held_order_ids(self) -> set[int]:
        return set(
            self._session.scalars(
                select(WarehouseQueueRow.order_id).where(WarehouseQueueRow.status == "held")
            ).all()
        )

    def next_position(self) -> int:
        rows = self.list_ordered()
        if not rows:
            return 1
        return max(r.position for r in rows) + 1

    def add(
        self, *, order_id: int, status: str = "waiting", note: str | None = None
    ) -> WarehouseQueueRow:
        if self.get_by_order_id(order_id) is not None:
            raise ValueError(f"Zlecenie #{order_id} jest już w kolejce.")
        row = WarehouseQueueRow(
            order_id=order_id,
            position=self.next_position(),
            status=status,
            note=note,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def delete_by_order_id(self, order_id: int) -> bool:
        row = self.get_by_order_id(order_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        self._repack_positions()
        return True

    def set_status(self, order_id: int, status: str) -> WarehouseQueueRow:
        row = self.get_by_order_id(order_id)
        if row is None:
            raise ValueError(f"Zlecenie #{order_id} nie jest w kolejce.")
        row.status = status
        self._session.flush()
        return row

    def swap_positions(self, order_id_a: int, order_id_b: int) -> None:
        a = self.get_by_order_id(order_id_a)
        b = self.get_by_order_id(order_id_b)
        if a is None or b is None:
            raise ValueError("Oba zlecenia muszą być w kolejce.")
        a.position, b.position = b.position, a.position
        self._session.flush()

    def _repack_positions(self) -> None:
        for idx, row in enumerate(self.list_ordered(), start=1):
            row.position = idx
        self._session.flush()
