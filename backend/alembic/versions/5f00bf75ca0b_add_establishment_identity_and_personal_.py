"""add establishment identity and personal signature stamp

Revision ID: 5f00bf75ca0b
Revises: a475b7e0dc91
Create Date: 2026-09-20 13:32:58.123147
"""
from alembic import op
import sqlalchemy as sa

revision = '5f00bf75ca0b'
down_revision = 'a475b7e0dc91'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("trade_name", sa.String(length=200), nullable=True))
    op.add_column("tenants", sa.Column("rccm", sa.String(length=50), nullable=True))
    op.add_column("tenants", sa.Column("ifu", sa.String(length=50), nullable=True))
    op.add_column("tenants", sa.Column("address", sa.String(length=300), nullable=True))
    op.add_column("tenants", sa.Column("logo_base64", sa.Text(), nullable=True))

    op.add_column("users", sa.Column("signature_base64", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("stamp_base64", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "stamp_base64")
    op.drop_column("users", "signature_base64")

    op.drop_column("tenants", "logo_base64")
    op.drop_column("tenants", "address")
    op.drop_column("tenants", "ifu")
    op.drop_column("tenants", "rccm")
    op.drop_column("tenants", "trade_name")
