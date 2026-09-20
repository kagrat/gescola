"""normalize enum values to lowercase

Revision ID: bb6bfdf29cc1
Revises: b7e388e822f9
Create Date: 2026-09-02 19:28:59.046731
"""
from alembic import op
import sqlalchemy as sa

revision = 'bb6bfdf29cc1'
down_revision = 'b7e388e822f9'
branch_labels = None
depends_on = None

# (nom du type, table, colonne, labels en minuscules dans l'ordre souhaité)
# Découverte pendant la revue : le type SQLAlchemy Enum stocke par défaut le
# NOM Python (majuscules) des membres plutôt que leur VALEUR (minuscules) sauf
# si `values_callable` est fourni — ce qui n'était pas le cas initialement.
# Cette migration corrige les 5 types enum du schéma pour qu'ils stockent des
# valeurs lisibles et cohérentes avec ce que l'API expose en JSON (ex:
# "school_admin" plutôt que "SCHOOL_ADMIN"), et corrige au passage
# l'incohérence introduite par la migration précédente (qui avait ajouté les
# nouveaux rôles directement en minuscules, alors que les rôles historiques
# étaient stockés en majuscules).
ENUM_MIGRATIONS = [
    (
        "user_role", "users", "role",
        ["super_admin", "school_admin", "censor", "supervisor", "accountant", "staff", "teacher", "parent"],
    ),
    ("student_status", "students", "status", ["active", "transferred", "graduated", "archived"]),
    ("attendance_status", "attendances", "status", ["present", "absent", "late"]),
    ("invoice_status", "invoices", "status", ["pending", "partially_paid", "paid", "overdue", "cancelled"]),
    ("payment_method", "payments", "method", ["cash", "mobile_money", "bank_transfer"]),
]


def upgrade() -> None:
    for type_name, table, column, labels in ENUM_MIGRATIONS:
        new_type = f"{type_name}_new"
        labels_sql = ", ".join(f"'{label}'" for label in labels)
        op.execute(f"CREATE TYPE {new_type} AS ENUM ({labels_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_type} "
            f"USING lower({column}::text)::{new_type}"
        )
        op.execute(f"DROP TYPE {type_name}")
        op.execute(f"ALTER TYPE {new_type} RENAME TO {type_name}")


def downgrade() -> None:
    # Retour aux labels historiques en MAJUSCULES (comportement par défaut de
    # SQLAlchemy sans values_callable), pour les 5 mêmes types.
    UPPER_LABELS = {
        "user_role": ["SUPER_ADMIN", "SCHOOL_ADMIN", "CENSOR", "SUPERVISOR", "ACCOUNTANT", "STAFF", "TEACHER", "PARENT"],
        "student_status": ["ACTIVE", "TRANSFERRED", "GRADUATED", "ARCHIVED"],
        "attendance_status": ["PRESENT", "ABSENT", "LATE"],
        "invoice_status": ["PENDING", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"],
        "payment_method": ["CASH", "MOBILE_MONEY", "BANK_TRANSFER"],
    }
    for type_name, table, column, _labels in ENUM_MIGRATIONS:
        new_type = f"{type_name}_old"
        labels_sql = ", ".join(f"'{label}'" for label in UPPER_LABELS[type_name])
        op.execute(f"CREATE TYPE {new_type} AS ENUM ({labels_sql})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_type} "
            f"USING upper({column}::text)::{new_type}"
        )
        op.execute(f"DROP TYPE {type_name}")
        op.execute(f"ALTER TYPE {new_type} RENAME TO {type_name}")
