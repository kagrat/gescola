"""row level security and email uniqueness

Revision ID: 3c234b5d9d72
Revises: a2f9d75fd121
Create Date: 2026-09-02 14:55:01.358161
"""
from alembic import op
import sqlalchemy as sa


revision = '3c234b5d9d72'
down_revision = 'a2f9d75fd121'
branch_labels = None
depends_on = None


TENANT_SCOPED_TABLES = [
    "school_classes",
    "subjects",
    "students",
    "grades",
    "attendances",
    "invoices",
    "payments",
]


def upgrade() -> None:
    # --- Unicité des e-mails ---
    # Un e-mail est unique PAR établissement (deux écoles peuvent avoir chacune
    # un contact@ecole... différent), et globalement unique pour les comptes
    # Super Administrateur (tenant_id NULL) — exprimé via deux contraintes
    # car un simple UNIQUE(tenant_id, email) ne bloque pas les doublons quand
    # tenant_id est NULL (NULL != NULL en SQL standard).
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])
    op.execute(
        "CREATE UNIQUE INDEX uq_users_global_email_super_admin "
        "ON users (email) WHERE tenant_id IS NULL"
    )

    # --- Row-Level Security ---
    # Défense en profondeur : même si une requête applicative oubliait le
    # filtre tenant_id (bug, régression future), PostgreSQL refuse toute
    # ligne dont le tenant_id ne correspond pas à la session en cours.
    # FORCE ROW LEVEL SECURITY : la policy s'applique même au propriétaire
    # de la table (le rôle applicatif gescola_app possède les tables ici).
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )


def downgrade() -> None:
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS uq_users_global_email_super_admin")
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
