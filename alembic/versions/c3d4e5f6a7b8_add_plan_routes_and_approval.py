"""add plan routes, sequence, and approval columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-10 22:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assignment_runs") as batch:
        batch.add_column(
            sa.Column("plan_status", sa.String(length=20), nullable=False, server_default="draft")
        )
        batch.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("approved_by", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("total_distance_km", sa.Float(), nullable=True))
        batch.add_column(sa.Column("total_cost_eur", sa.Float(), nullable=True))

    with op.batch_alter_table("assignment_items") as batch:
        batch.add_column(sa.Column("sequence", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("drop_key", sa.String(length=200), nullable=True))

    op.create_table(
        "assignment_routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("vehicle_code", sa.String(length=50), nullable=False),
        sa.Column("drop_count", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("cost_eur", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["assignment_runs.id"],
            name=op.f("fk_assignment_routes_run_id_assignment_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_routes")),
    )


def downgrade() -> None:
    op.drop_table("assignment_routes")
    with op.batch_alter_table("assignment_items") as batch:
        batch.drop_column("drop_key")
        batch.drop_column("sequence")
    with op.batch_alter_table("assignment_runs") as batch:
        batch.drop_column("total_cost_eur")
        batch.drop_column("total_distance_km")
        batch.drop_column("approved_by")
        batch.drop_column("approved_at")
        batch.drop_column("plan_status")
