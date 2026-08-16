"""add optional kg_per_pallet override on orders

Revision ID: f6a7b8c9d0e1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-15 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {col["name"] for col in inspector.get_columns("orders")}
    if "kg_per_pallet" not in columns:
        with op.batch_alter_table("orders") as batch:
            batch.add_column(sa.Column("kg_per_pallet", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("kg_per_pallet")
