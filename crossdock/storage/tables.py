"""ORM table definitions (SQLAlchemy 2.0 declarative).

Naming convention on metadata is required for Alembic batch mode
(ALTER TABLE emulation) to work reliably on SQLite.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_code: Mapped[str] = mapped_column(String(100), index=True)
    pickup_name: Mapped[str] = mapped_column(String(200))
    pickup_city: Mapped[str | None] = mapped_column(String(100))
    pickup_country: Mapped[str | None] = mapped_column(String(10))
    pickup_postal_code: Mapped[str | None] = mapped_column(String(20))
    pickup_latitude: Mapped[float | None]
    pickup_longitude: Mapped[float | None]
    delivery_name: Mapped[str] = mapped_column(String(200))
    delivery_city: Mapped[str | None] = mapped_column(String(100))
    delivery_country: Mapped[str | None] = mapped_column(String(10))
    delivery_postal_code: Mapped[str | None] = mapped_column(String(20))
    delivery_latitude: Mapped[float | None]
    delivery_longitude: Mapped[float | None]
    delivery_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    shipments: Mapped[list["ShipmentRow"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class ShipmentRow(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT at the schema level backs the FR-019 inseparability rule:
    # a shipment cannot exist or be moved without its parent order.
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    shipment_number: Mapped[str] = mapped_column(String(100), index=True)
    pallet_count: Mapped[int | None]
    weight_kg: Mapped[float | None]

    order: Mapped[OrderRow] = relationship(back_populates="shipments")


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    username: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str | None] = mapped_column(String)  # JSON as TEXT


class VehicleRow(Base):
    """Fleet vehicle. Seed rows are placeholders until Martyna's table (W-03)."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(20))
    pallet_capacity: Mapped[int]
    weight_capacity_kg: Mapped[float]
    is_active: Mapped[bool] = mapped_column(default=True)
    is_placeholder: Mapped[bool] = mapped_column(default=True)
    is_busy: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LocationCoordsRow(Base):
    """MVP coordinate dictionary (manual / seeded; Photon later)."""

    __tablename__ = "location_coords"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_key: Mapped[str] = mapped_column(String(400), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(10))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float]
    longitude: Mapped[float]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AssignmentRunRow(Base):
    """One plan run: CP-SAT assignment + routing (T3/T4)."""

    __tablename__ = "assignment_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    username: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    wall_time_s: Mapped[float]
    unassigned_count: Mapped[int]
    warnings_json: Mapped[str | None] = mapped_column(String)
    plan_status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_distance_km: Mapped[float | None]
    total_cost_eur: Mapped[float | None]

    items: Mapped[list["AssignmentItemRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    routes: Mapped[list["AssignmentRouteRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AssignmentItemRow(Base):
    """Order assigned to a vehicle within an assignment run."""

    __tablename__ = "assignment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("assignment_runs.id", ondelete="CASCADE"))
    vehicle_id: Mapped[int | None]
    vehicle_code: Mapped[str] = mapped_column(String(50))
    order_id: Mapped[int]
    delivery_code: Mapped[str] = mapped_column(String(100))
    weight_kg: Mapped[float]
    fill_ratio: Mapped[float | None]
    sequence: Mapped[int | None]
    drop_key: Mapped[str | None] = mapped_column(String(200))

    run: Mapped[AssignmentRunRow] = relationship(back_populates="items")


class AssignmentRouteRow(Base):
    """Per-vehicle route metrics for a plan run (T4)."""

    __tablename__ = "assignment_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("assignment_runs.id", ondelete="CASCADE"))
    vehicle_id: Mapped[int | None]
    vehicle_code: Mapped[str] = mapped_column(String(50))
    drop_count: Mapped[int]
    distance_km: Mapped[float]
    cost_eur: Mapped[float]
    route_status: Mapped[str] = mapped_column(String(20), default="proposed")

    run: Mapped[AssignmentRunRow] = relationship(back_populates="routes")


class WarehouseQueueRow(Base):
    """Manual warehouse queue entry — whole orders only (FR-019 / FR-020)."""

    __tablename__ = "warehouse_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    position: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
