"""add platform billing

Revision ID: a475b7e0dc91
Revises: fb4f296e97f0
Create Date: 2026-09-20 11:54:38.384921
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'a475b7e0dc91'
down_revision = 'fb4f296e97f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE subscription_status AS ENUM ('trialing', 'active', 'past_due', 'suspended', 'canceled')")
    op.execute("CREATE TYPE platform_invoice_status AS ENUM ('pending', 'paid', 'overdue', 'cancelled')")
    op.execute("CREATE TYPE platform_payment_method AS ENUM ('mobile_money', 'bank_transfer', 'cash')")

    op.create_table(
        "platform_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("price_per_month", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_students", sa.Integer(), nullable=True),
        sa.Column("is_default_trial_plan", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", postgresql.ENUM("trialing", "active", "past_due", "suspended", "canceled", name="subscription_status", create_type=False), nullable=False),
        sa.Column("trial_ends_at", sa.Date(), nullable=True),
        sa.Column("current_period_end", sa.Date(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "platform_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount_due", sa.Numeric(10, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "paid", "overdue", "cancelled", name="platform_invoice_status", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "platform_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_invoices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", postgresql.ENUM("mobile_money", "bank_transfer", "cash", name="platform_payment_method", create_type=False), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Plan d'essai gratuit par défaut : nécessaire dès le premier déploiement
    # pour que /auth/signup fonctionne sans étape de configuration manuelle.
    op.execute(
        f"""
        INSERT INTO platform_plans (id, name, code, price_per_month, max_students, is_default_trial_plan, is_active, created_at, updated_at)
        VALUES ('{uuid.uuid4()}', 'Essai gratuit', 'essai-gratuit', 0, 100, true, true, now(), now())
        """
    )


def downgrade() -> None:
    op.drop_table("platform_payments")
    op.drop_table("platform_invoices")
    op.drop_table("subscriptions")
    op.drop_table("platform_plans")
    op.execute("DROP TYPE platform_payment_method")
    op.execute("DROP TYPE platform_invoice_status")
    op.execute("DROP TYPE subscription_status")
