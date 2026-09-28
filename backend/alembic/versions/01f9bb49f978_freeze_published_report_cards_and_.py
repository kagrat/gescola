"""freeze published report cards and designated signers

Revision ID: 01f9bb49f978
Revises: 07166aebe589
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '01f9bb49f978'
down_revision = '07166aebe589'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("bulletin_director_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tenants", sa.Column("bulletin_censor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("report_cards", sa.Column("frozen", postgresql.JSONB(), nullable=True))
    op.create_table(
        "report_card_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("data_uri", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_report_card_asset"),
    )
    op.execute("ALTER TABLE report_card_assets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE report_card_assets FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_report_card_assets ON report_card_assets "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_report_card_assets ON report_card_assets")
    op.drop_table("report_card_assets")
    op.drop_column("report_cards", "frozen")
    op.drop_column("tenants", "bulletin_censor_user_id")
    op.drop_column("tenants", "bulletin_director_user_id")
