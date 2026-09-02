"""add route lifecycle timestamps

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-09-02 08:31:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    with op.batch_alter_table("assignment_routes") as batch:
        if not _has_column("assignment_routes", "approved_at"):
            batch.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        if not _has_column("assignment_routes", "departed_at"):
            batch.add_column(sa.Column("departed_at", sa.DateTime(), nullable=True))
        if not _has_column("assignment_routes", "completed_at"):
            batch.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assignment_routes") as batch:
        if _has_column("assignment_routes", "completed_at"):
            batch.drop_column("completed_at")
        if _has_column("assignment_routes", "departed_at"):
            batch.drop_column("departed_at")
        if _has_column("assignment_routes", "approved_at"):
            batch.drop_column("approved_at")
