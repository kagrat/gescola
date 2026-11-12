"""receipts numbering, certificates, public document verification (AU-10)

Revision ID: e8a41b7d3c92
Revises: d3f7a19c5e60
"""
import secrets

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8a41b7d3c92"
down_revision = "d3f7a19c5e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("receipt_counter", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tenants", sa.Column("certificate_counter", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "document_verifications",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("kind", "ref_id", name="uq_document_verification_ref"),
    )
    op.create_index("ix_document_verifications_tenant", "document_verifications", ["tenant_id"])

    # Reçus : numérotation des paiements existants, établissement par établissement,
    # dans l'ordre où ils ont été saisis. `payments` est sous RLS (FORCE).
    op.add_column("payments", sa.Column("receipt_number", sa.Integer(), nullable=True))
    conn = op.get_bind()
    for (tenant_id,) in conn.execute(sa.text("SELECT id FROM tenants")).all():
        conn.execute(sa.text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)})
        rows = conn.execute(
            sa.text("SELECT id FROM payments WHERE tenant_id = :t ORDER BY created_at, id"), {"t": tenant_id}
        ).all()
        for n, (payment_id,) in enumerate(rows, start=1):
            conn.execute(sa.text("UPDATE payments SET receipt_number = :n WHERE id = :i"), {"n": n, "i": payment_id})
            conn.execute(
                sa.text("INSERT INTO document_verifications (code, tenant_id, kind, ref_id) VALUES (:c, :t, 'receipt', :i)"),
                {"c": secrets.token_urlsafe(12), "t": tenant_id, "i": payment_id},
            )
        conn.execute(sa.text("UPDATE tenants SET receipt_counter = :n WHERE id = :t"), {"n": len(rows), "t": tenant_id})
    op.alter_column("payments", "receipt_number", nullable=False)  # échoue bruyamment si une ligne a échappé
    op.create_unique_constraint("uq_payment_receipt_number", "payments", ["tenant_id", "receipt_number"])

    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "academic_year", name="uq_certificate_student_year"),
    )
    op.execute("ALTER TABLE certificates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE certificates FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_certificates ON certificates "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_certificates ON certificates")
    op.drop_table("certificates")
    op.drop_constraint("uq_payment_receipt_number", "payments", type_="unique")
    op.drop_column("payments", "receipt_number")
    op.drop_table("document_verifications")
    op.drop_column("tenants", "certificate_counter")
    op.drop_column("tenants", "receipt_counter")
