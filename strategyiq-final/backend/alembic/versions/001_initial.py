"""Initial StrategyIQ schema.

Revision ID: 001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("tier", sa.String(20), server_default="beginner"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("tier", sa.String(20), server_default="beginner"),
        sa.Column("active", sa.Boolean(), server_default="false"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "query_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("endpoint", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), index=True),
        sa.Column("symbol", sa.String(20), index=True),
        sa.Column("weight", sa.Float()),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "portfolio_var_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), index=True),
        sa.Column("celery_task_id", sa.String(255), index=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("var_95", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "price_ticks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(20), index=True),
        sa.Column("price", sa.Float()),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("source", sa.String(20), server_default="polygon"),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.execute("SELECT create_hypertable('price_ticks', 'ts', if_not_exists => TRUE)")


def downgrade() -> None:
    op.drop_table("price_ticks")
    op.drop_table("portfolio_var_jobs")
    op.drop_table("holdings")
    op.drop_table("portfolios")
    op.drop_table("query_logs")
    op.drop_table("subscriptions")
    op.drop_table("users")
