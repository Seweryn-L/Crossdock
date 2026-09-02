"""add must_leave_by on orders

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-09-02 08:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {col["name"] for col in inspector.get_columns("orders")}
    if "must_leave_by" not in columns:
        with op.batch_alter_table("orders") as batch:
            batch.add_column(sa.Column("must_leave_by", sa.Date(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE orders SET must_leave_by = date(delivery_date, '-2 days') "
            "WHERE must_leave_by IS NULL"
        )
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {col["name"] for col in inspector.get_columns("orders")}
    if "must_leave_by" in columns:
        with op.batch_alter_table("orders") as batch:
            batch.drop_column("must_leave_by")
