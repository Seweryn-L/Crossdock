"""add assignment_runs and assignment_items

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-10 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assignment_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("wall_time_s", sa.Float(), nullable=False),
        sa.Column("unassigned_count", sa.Integer(), nullable=False),
        sa.Column("warnings_json", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_runs")),
    )
    op.create_table(
        "assignment_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("vehicle_code", sa.String(length=50), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("delivery_code", sa.String(length=100), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("fill_ratio", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["assignment_runs.id"],
            name=op.f("fk_assignment_items_run_id_assignment_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_items")),
    )


def downgrade() -> None:
    op.drop_table("assignment_items")
    op.drop_table("assignment_runs")
