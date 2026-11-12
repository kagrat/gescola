"""fee plans (barème par niveau) and student fee discount (CP-01)

Revision ID: f1b9c2d4e7a5
Revises: e8a41b7d3c92
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f1b9c2d4e7a5"
down_revision = "e8a41b7d3c92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Colonne à valeur par défaut : les élèves existants n'ont aucune remise (0 %), sans rattrapage à faire.
    op.add_column("students", sa.Column("fee_discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.add_column("students", sa.Column("fee_discount_reason", sa.String(200), nullable=True))
    op.create_check_constraint("ck_students_fee_discount", "students", "fee_discount_percent >= 0 AND fee_discount_percent <= 100")

    op.create_table(
        "fee_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("level", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("installments", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "level", "name", name="uq_fee_plan_level_name"),
    )
    op.execute("ALTER TABLE fee_plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fee_plans FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_fee_plans ON fee_plans "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_fee_plans ON fee_plans")
    op.drop_table("fee_plans")
    op.drop_constraint("ck_students_fee_discount", "students", type_="check")
    op.drop_column("students", "fee_discount_reason")
    op.drop_column("students", "fee_discount_percent")
