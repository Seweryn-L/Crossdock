"""add route_status and vehicle is_busy

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-11 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicles") as batch:
        batch.add_column(
            sa.Column("is_busy", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("assignment_routes") as batch:
        batch.add_column(
            sa.Column(
                "route_status",
                sa.String(length=20),
                nullable=False,
                server_default="proposed",
            )
        )
        batch.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("approved_by", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assignment_routes") as batch:
        batch.drop_column("approved_by")
        batch.drop_column("approved_at")
        batch.drop_column("route_status")
    with op.batch_alter_table("vehicles") as batch:
        batch.drop_column("is_busy")
