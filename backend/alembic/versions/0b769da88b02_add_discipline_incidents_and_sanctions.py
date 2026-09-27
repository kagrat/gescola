"""add discipline incidents and sanctions

Revision ID: 0b769da88b02
Revises: 566c46aded10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0b769da88b02'
down_revision = '566c46aded10'
branch_labels = None
depends_on = None

TENANT_SCOPED_NEW_TABLES = ["incidents", "sanctions"]


def upgrade() -> None:
    op.execute("CREATE TYPE incident_category AS ENUM ('behavior', 'violence', 'property_damage', 'cheating', 'repeated_lateness', 'other')")
    op.execute("CREATE TYPE incident_severity AS ENUM ('minor', 'moderate', 'serious')")
    op.execute("CREATE TYPE incident_status AS ENUM ('reported', 'under_review', 'resolved')")
    op.execute("CREATE TYPE sanction_type AS ENUM ('warning', 'detention', 'extra_work', 'parent_summon', 'temporary_exclusion', 'other')")

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reported_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", postgresql.ENUM("behavior", "violence", "property_damage", "cheating", "repeated_lateness", "other", name="incident_category", create_type=False), nullable=False),
        sa.Column("severity", postgresql.ENUM("minor", "moderate", "serious", name="incident_severity", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM("reported", "under_review", "resolved", name="incident_status", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sanctions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("imposed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sanction_type", postgresql.ENUM("warning", "detention", "extra_work", "parent_summon", "temporary_exclusion", "other", name="sanction_type", create_type=False), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    for table in TENANT_SCOPED_NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TENANT_SCOPED_NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
    op.drop_table("sanctions")
    op.drop_table("incidents")
    op.execute("DROP TYPE sanction_type")
    op.execute("DROP TYPE incident_status")
    op.execute("DROP TYPE incident_severity")
    op.execute("DROP TYPE incident_category")
