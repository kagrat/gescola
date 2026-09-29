"""attendance unique per day and bulk roll call support

Revision ID: 7771cb2546c3
Revises: 2c9700e39485
"""
from alembic import op
import sqlalchemy as sa

revision = '7771cb2546c3'
down_revision = '2c9700e39485'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aucune contrainte n'empêchait jusqu'ici deux enregistrements de présence pour le
    # même élève le même jour (deux appels distincts, ou un double clic, créaient deux
    # lignes contradictoires). On s'arrête avec un message explicite si des doublons
    # existent déjà plutôt que de choisir arbitrairement lequel garder à la place de
    # l'exploitant.
    duplicates = op.get_bind().execute(
        sa.text(
            "SELECT tenant_id, student_id, date, count(*) AS n FROM attendances "
            "GROUP BY tenant_id, student_id, date HAVING count(*) > 1 LIMIT 10"
        )
    ).fetchall()
    if duplicates:
        listing = ", ".join(f"élève {row.student_id} le {row.date} ({row.n} lignes)" for row in duplicates)
        raise RuntimeError(
            "Migration interrompue : plusieurs enregistrements de présence existent pour le même élève le même "
            "jour (" + listing + "). Corrigez ces doublons (conservez le plus récent, supprimez les autres) "
            "puis relancez la migration."
        )
    op.create_unique_constraint("uq_attendance_student_date", "attendances", ["tenant_id", "student_id", "date"])


def downgrade() -> None:
    op.drop_constraint("uq_attendance_student_date", "attendances", type_="unique")
