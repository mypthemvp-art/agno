"""Add holdings table and portfolio_var_jobs for Celery VaR tasks.

Revision ID: 002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), index=True),
        sa.Column("symbol", sa.String(20), index=True, nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("cost_basis", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "portfolio_var_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), index=True),
        sa.Column("celery_task_id", sa.String(255), index=True, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("var_95", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("portfolio_var_jobs")
    op.drop_table("holdings")
