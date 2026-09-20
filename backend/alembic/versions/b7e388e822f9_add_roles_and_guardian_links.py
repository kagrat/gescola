"""add roles and guardian links

Revision ID: b7e388e822f9
Revises: 3c234b5d9d72
Create Date: 2026-09-02 19:25:09.638256
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'b7e388e822f9'
down_revision = '3c234b5d9d72'
branch_labels = None
depends_on = None

NEW_ROLES = ["censor", "supervisor", "accountant"]


def upgrade() -> None:
    # --- Nouveaux rôles internes à l'établissement ---
    # ALTER TYPE ... ADD VALUE est transactionnel depuis PostgreSQL 12 ; la
    # nouvelle valeur ne peut simplement pas être UTILISÉE dans la même
    # transaction que celle qui la crée — ce n'est pas le cas ici, cette
    # migration ne fait qu'ajouter les valeurs, sans écrire de ligne.
    for role in NEW_ROLES:
        op.execute(f"ALTER TYPE user_role ADD VALUE IF NOT EXISTS '{role}'")

    # --- Table de rattachement parent <-> élève ---
    op.create_table(
        "guardian_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parent_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("relationship_label", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parent_user_id", "student_id", name="uq_guardian_link_parent_student"),
    )

    op.execute("ALTER TABLE guardian_links ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE guardian_links FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_guardian_links ON guardian_links "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_guardian_links ON guardian_links")
    op.drop_table("guardian_links")
    # PostgreSQL ne permet pas de retirer une valeur d'un type ENUM existant
    # sans recréer le type entièrement ; les rôles ajoutés restent donc en
    # place lors d'un downgrade (choix documenté, sans impact fonctionnel
    # tant qu'aucun utilisateur n'utilise ces rôles).
