"""add optional display_name on assignment_runs

Revision ID: a9b0c1d2e3f4
Revises: e5f6a7b8c9d0
Create Date: 2026-08-16 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("assignment_runs", "display_name"):
        with op.batch_alter_table("assignment_runs") as batch:
            batch.add_column(sa.Column("display_name", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assignment_runs") as batch:
        batch.drop_column("display_name")
