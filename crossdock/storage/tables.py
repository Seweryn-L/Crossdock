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
