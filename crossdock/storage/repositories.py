"""Repositories — the only place that touches ORM sessions directly."""

from __future__ import annotations

import json
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
    AssignmentRunRow,
    AuditLogRow,
    LocationCoordsRow,
    OrderRow,
    ShipmentRow,
    UserRow,
    VehicleRow,
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

    def get_by_id(self, order_id: int) -> Order | None:
        row = self._session.scalar(
            select(OrderRow)
            .options(selectinload(OrderRow.shipments))
            .where(OrderRow.id == order_id)
        )
        return _to_domain_order(row) if row else None


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

    def count(self) -> int:
        return len(self._session.scalars(select(VehicleRow.id)).all())

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
        )
        self._session.add(row)
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
        run = AssignmentRunRow(
            username=username,
            status=status,
            wall_time_s=wall_time_s,
            unassigned_count=len(unassigned_order_ids),
            warnings_json=json.dumps(warnings, ensure_ascii=False) if warnings else None,
        )
        self._session.add(run)
        self._session.flush()

        for load in loads:
            fill = load.get("fill_ratio")
            for order_id in load["order_ids"]:
                code, weight = order_meta.get(int(order_id), ("?", 0.0))
                self._session.add(
                    AssignmentItemRow(
                        run_id=run.id,
                        vehicle_id=load.get("vehicle_id"),
                        vehicle_code=str(load["vehicle_code"]),
                        order_id=int(order_id),
                        delivery_code=code,
                        weight_kg=weight,
                        fill_ratio=fill,
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
                )
            )
        self._session.flush()
        return run.id

    def get_latest_run_id(self) -> int | None:
        row = self._session.scalar(
            select(AssignmentRunRow).order_by(AssignmentRunRow.id.desc()).limit(1)
        )
        return row.id if row else None

    def list_items_for_run(self, run_id: int) -> list[AssignmentItemRow]:
        return list(
            self._session.scalars(
                select(AssignmentItemRow)
                .where(AssignmentItemRow.run_id == run_id)
                .order_by(AssignmentItemRow.vehicle_code, AssignmentItemRow.delivery_code)
            ).all()
        )
