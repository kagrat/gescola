"""add mfa fields to users

Revision ID: cf07632250e0
Revises: bb6bfdf29cc1
Create Date: 2026-09-03 11:52:14.842174
"""
from alembic import op
import sqlalchemy as sa

revision = 'cf07632250e0'
down_revision = 'bb6bfdf29cc1'
branch_labels = None
depends_on = None

# NOTE : l'autogenerate proposait aussi de supprimer uq_users_tenant_email et
# uq_users_global_email_super_admin — ces contraintes ont été créées par SQL
# brut dans une migration antérieure (pas via les métadonnées du modèle
# SQLAlchemy), Alembic ne les reconnaît donc pas et les croit orphelines.
# Elles sont volontairement conservées : les retirer romprait l'unicité des
# e-mails vérifiée par test_academic_and_users.py::test_duplicate_email_within_same_tenant_rejected.


def upgrade() -> None:
    op.add_column('users', sa.Column('mfa_secret', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    # server_default retiré après coup : nécessaire seulement pour remplir les
    # lignes existantes, pas souhaitable comme défaut implicite permanent du
    # schéma (le modèle Python porte déjà default=False à l'écriture).
    op.alter_column('users', 'mfa_enabled', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_secret')
