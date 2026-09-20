"""add notifications table

Revision ID: 4251158e2e6e
Revises: cf07632250e0
Create Date: 2026-09-03 11:54:29.809691
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '4251158e2e6e'
down_revision = 'cf07632250e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE notification_type AS ENUM "
        "('invoice_reminder', 'grade_published', 'attendance_alert', 'general')"
    )
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", postgresql.ENUM("invoice_reminder", "grade_published", "attendance_alert", "general", name="notification_type", create_type=False), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_notifications ON notifications "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_notifications ON notifications")
    op.drop_table("notifications")
    op.execute("DROP TYPE notification_type")
