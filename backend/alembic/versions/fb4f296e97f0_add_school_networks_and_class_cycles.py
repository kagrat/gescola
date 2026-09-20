"""add school networks and class cycles

Revision ID: fb4f296e97f0
Revises: c24ba8c8b62b
Create Date: 2026-09-18 12:01:59.625481
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'fb4f296e97f0'
down_revision = 'c24ba8c8b62b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Réseaux d'établissements (pas de RLS : consultés uniquement via
    # network_reporting_service, qui bascule le contexte tenant établissement
    # par établissement plutôt que de lire à travers plusieurs tenants) ---
    op.create_table(
        "school_networks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column("tenants", sa.Column("network_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_networks.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_tenants_network_id", "tenants", ["network_id"])

    op.add_column("users", sa.Column("network_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_networks.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_users_network_id", "users", ["network_id"])

    # --- Nouveau rôle NETWORK_ADMIN ---
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'network_admin'")

    # --- Cycles scolaires sur les classes ---
    op.execute("CREATE TYPE school_cycle AS ENUM ('maternelle', 'primaire', 'secondaire')")
    op.add_column(
        "school_classes",
        sa.Column(
            "cycle",
            postgresql.ENUM("maternelle", "primaire", "secondaire", name="school_cycle", create_type=False),
            nullable=False,
            server_default="primaire",
        ),
    )
    # server_default retiré après coup : nécessaire seulement pour remplir les
    # classes déjà existantes, le modèle Python porte déjà son propre défaut.
    op.alter_column("school_classes", "cycle", server_default=None)


def downgrade() -> None:
    op.drop_column("school_classes", "cycle")
    op.execute("DROP TYPE school_cycle")

    op.drop_index("ix_users_network_id", table_name="users")
    op.drop_column("users", "network_id")
    op.drop_index("ix_tenants_network_id", table_name="tenants")
    op.drop_column("tenants", "network_id")

    op.drop_table("school_networks")
    # La valeur 'network_admin' du type user_role n'est pas retirée (PostgreSQL
    # ne le permet pas sans recréer le type) — sans impact tant qu'aucun
    # utilisateur ne porte ce rôle après le downgrade.
