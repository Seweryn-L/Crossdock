"""add attention_reason on assignment_items

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-09-02 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("assignment_items", "attention_reason"):
        op.add_column(
            "assignment_items",
            sa.Column("attention_reason", sa.String(length=40), nullable=True),
        )


def downgrade() -> None:
    if _has_column("assignment_items", "attention_reason"):
        op.drop_column("assignment_items", "attention_reason")
