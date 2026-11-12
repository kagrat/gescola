"""academic year on grades + student enrollment history (AU-07)

Revision ID: 9c5e2b7a41d8
Revises: 8a41d0c3e9b2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9c5e2b7a41d8"
down_revision = "8a41d0c3e9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Figer l'année courante des établissements qui ne l'avaient jamais réglée
    #    (sinon elle changerait toute seule au 1er septembre). `tenants` n'est
    #    pas soumise à la RLS.
    op.execute(
        """
        UPDATE tenants SET academic_year =
            CASE WHEN extract(month FROM now()) >= 9
                 THEN extract(year FROM now())::int || '-' || (extract(year FROM now())::int + 1)
                 ELSE (extract(year FROM now())::int - 1) || '-' || extract(year FROM now())::int
            END
        WHERE academic_year IS NULL
        """
    )

    # 2. Année sur les notes. Aucun passage d'année n'a pu avoir lieu avant
    #    cette migration : toutes les notes existantes appartiennent à l'année
    #    courante de leur établissement. `grades` est sous RLS (FORCE) : on
    #    rattrape établissement par établissement, avec le contexte posé.
    op.add_column("grades", sa.Column("academic_year", sa.String(9), nullable=True))
    conn = op.get_bind()
    for tenant_id, year in conn.execute(sa.text("SELECT id, academic_year FROM tenants")).all():
        conn.execute(sa.text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)})
        conn.execute(sa.text("UPDATE grades SET academic_year = :y WHERE tenant_id = :t"), {"y": year, "t": tenant_id})
    # Échoue bruyamment (et annule tout) si une note a échappé au rattrapage.
    op.alter_column("grades", "academic_year", nullable=False)
    op.create_index("ix_grades_tenant_year_term", "grades", ["tenant_id", "academic_year", "term"])

    # 3. Historique des parcours.
    op.create_table(
        "student_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_name", sa.String(100), nullable=False),
        sa.Column("outcome", postgresql.ENUM("promoted", "repeated", "graduated", name="enrollment_outcome"), nullable=False),
        sa.Column("next_class_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "academic_year", name="uq_enrollment_student_year"),
    )
    op.create_index("ix_enrollments_tenant_year", "student_enrollments", ["tenant_id", "academic_year"])
    op.execute("ALTER TABLE student_enrollments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_enrollments FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_student_enrollments ON student_enrollments "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_student_enrollments ON student_enrollments")
    op.drop_table("student_enrollments")
    op.execute("DROP TYPE IF EXISTS enrollment_outcome")
    op.drop_index("ix_grades_tenant_year_term", table_name="grades")
    op.drop_column("grades", "academic_year")
