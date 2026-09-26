"""add founder role

Revision ID: 8779a74fc82b
Revises: 132397b094f0
Create Date: 2026-09-26 18:59:31.898308
"""
from alembic import op
import sqlalchemy as sa

revision = '8779a74fc82b'
down_revision = '132397b094f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'founder'")


def downgrade() -> None:
    # La valeur 'founder' du type user_role n'est pas retirée (PostgreSQL ne
    # le permet pas sans recréer le type) — sans impact tant qu'aucun compte
    # ne porte ce rôle après le downgrade.
    pass
