"""indexes for paginated student listing and search

Revision ID: 8a41d0c3e9b2
Revises: 7771cb2546c3
"""
from alembic import op

revision = '8a41d0c3e9b2'
down_revision = '7771cb2546c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tri stable de la liste (nom, prénom, id) borné à l'établissement.
    op.create_index("ix_students_tenant_name", "students", ["tenant_id", "last_name", "first_name", "id"])
    # Listes de classe et filtres par statut (appel, bulletins, effectifs).
    op.create_index("ix_students_tenant_class_status", "students", ["tenant_id", "class_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_students_tenant_class_status", table_name="students")
    op.drop_index("ix_students_tenant_name", table_name="students")
