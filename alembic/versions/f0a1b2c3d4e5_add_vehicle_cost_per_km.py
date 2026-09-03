"""add vehicles.cost_per_km nullable override

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-09-03 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("vehicles", "cost_per_km"):
        op.add_column(
            "vehicles",
            sa.Column("cost_per_km", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("vehicles", "cost_per_km"):
        op.drop_column("vehicles", "cost_per_km")
