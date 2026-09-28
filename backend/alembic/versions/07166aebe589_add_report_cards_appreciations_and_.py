"""add report cards, appreciations and bulletin settings

Revision ID: 07166aebe589
Revises: 0b769da88b02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '07166aebe589'
down_revision = '0b769da88b02'
branch_labels = None
depends_on = None

TENANT_SCOPED_NEW_TABLES = ["subject_appreciations", "report_cards"]


def upgrade() -> None:
    # --- Élèves : informations administratives du bulletin ---
    op.execute("CREATE TYPE student_gender AS ENUM ('male', 'female')")
    op.add_column("students", sa.Column("matricule", sa.String(length=30), nullable=True))
    op.add_column("students", sa.Column("gender", postgresql.ENUM("male", "female", name="student_gender", create_type=False), nullable=True))
    op.add_column("students", sa.Column("is_repeater", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("CREATE UNIQUE INDEX uq_students_tenant_matricule ON students (tenant_id, matricule) WHERE matricule IS NOT NULL")

    # --- Classes : professeur principal ---
    op.add_column("school_classes", sa.Column("head_teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    # --- Établissement : réglages du bulletin ---
    op.add_column("tenants", sa.Column("academic_year", sa.String(length=9), nullable=True))
    op.add_column("tenants", sa.Column("bulletin_motto", sa.String(length=200), nullable=True))
    op.add_column("tenants", sa.Column("bulletin_authority_header", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("bulletin_place", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("bulletin_show_appreciations", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenants", sa.Column("bulletin_show_school_life", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenants", sa.Column("bulletin_show_head_teacher_signature", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenants", sa.Column("term_periods", postgresql.JSONB(), nullable=True))

    # --- Appréciations et bulletins ---
    op.execute("CREATE TYPE report_card_status AS ENUM ('draft', 'published')")
    op.create_table(
        "subject_appreciations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(length=10), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "subject_id", "term", name="uq_subject_appreciation"),
    )
    op.create_table(
        "report_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("term", sa.String(length=10), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "published", name="report_card_status", create_type=False), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("principal_comment", sa.Text(), nullable=True),
        sa.Column("council_decision", sa.String(length=200), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "term", "academic_year", name="uq_report_card_student_term"),
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
    op.drop_table("report_cards")
    op.drop_table("subject_appreciations")
    op.execute("DROP TYPE report_card_status")
    for col in ["term_periods", "bulletin_show_head_teacher_signature", "bulletin_show_school_life",
                "bulletin_show_appreciations", "bulletin_place", "bulletin_authority_header", "bulletin_motto", "academic_year"]:
        op.drop_column("tenants", col)
    op.drop_column("school_classes", "head_teacher_id")
    op.execute("DROP INDEX IF EXISTS uq_students_tenant_matricule")
    op.drop_column("students", "is_repeater")
    op.drop_column("students", "gender")
    op.drop_column("students", "matricule")
    op.execute("DROP TYPE student_gender")
