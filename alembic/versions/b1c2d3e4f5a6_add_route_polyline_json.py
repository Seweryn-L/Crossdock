"""add polyline_json on assignment_routes for OSRM geometries

Revision ID: b1c2d3e4f5a6
Revises: a9b0c1d2e3f4
Create Date: 2026-08-20 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("assignment_routes", "polyline_json"):
        with op.batch_alter_table("assignment_routes") as batch:
            batch.add_column(sa.Column("polyline_json", sa.String(), nullable=True))


def downgrade() -> None:
    if _has_column("assignment_routes", "polyline_json"):
        with op.batch_alter_table("assignment_routes") as batch:
            batch.drop_column("polyline_json")
