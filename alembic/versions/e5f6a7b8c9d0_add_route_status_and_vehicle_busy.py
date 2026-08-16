"""add route_status on assignment_routes and is_busy on vehicles

Revision ID: e5f6a7b8c9d0
Revises: f6a7b8c9d0e1
Create Date: 2026-08-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("vehicles", "is_busy"):
        with op.batch_alter_table("vehicles") as batch:
            batch.add_column(
                sa.Column("is_busy", sa.Boolean(), nullable=False, server_default=sa.false())
            )
    if not _has_column("assignment_routes", "route_status"):
        with op.batch_alter_table("assignment_routes") as batch:
            batch.add_column(
                sa.Column(
                    "route_status",
                    sa.String(length=20),
                    nullable=False,
                    server_default="proposed",
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("assignment_routes") as batch:
        batch.drop_column("route_status")
    with op.batch_alter_table("vehicles") as batch:
        batch.drop_column("is_busy")
