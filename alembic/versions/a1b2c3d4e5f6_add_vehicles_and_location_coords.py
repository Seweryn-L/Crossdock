"""add vehicles and location_coords

Revision ID: a1b2c3d4e5f6
Revises: 38bf6baa23f9
Create Date: 2026-07-20 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "38bf6baa23f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("vehicle_type", sa.String(length=20), nullable=False),
        sa.Column("pallet_capacity", sa.Integer(), nullable=False),
        sa.Column("weight_capacity_kg", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_placeholder", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicles")),
        sa.UniqueConstraint("code", name=op.f("uq_vehicles_code")),
    )
    op.create_table(
        "location_coords",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("location_key", sa.String(length=400), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=10), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location_coords")),
        sa.UniqueConstraint("location_key", name=op.f("uq_location_coords_location_key")),
    )


def downgrade() -> None:
    op.drop_table("location_coords")
    op.drop_table("vehicles")
