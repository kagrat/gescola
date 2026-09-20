import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class TeacherAssignment(Base, TenantScopedMixin, TimestampMixin):
    """Affecte un enseignant à une matière, pour une classe donnée — reflète
    l'organisation réelle d'un établissement (« M. Dupont enseigne les
    Mathématiques en 6ème A »).

    Sert à deux choses :
      1. Construire l'emploi du temps (chaque créneau référence une
         affectation implicite classe+matière+enseignant cohérente).
      2. Restreindre la saisie des notes : un enseignant AYANT AU MOINS UNE
         affectation enregistrée ne peut noter que ses classes/matières
         assignées (voir grade_service). Un enseignant sans aucune
         affectation reste non restreint (grandfathering, cohérent avec le
         reste du projet) — utile en période de configuration initiale d'un
         établissement, avant que les affectations n'aient été saisies.
    """

    __tablename__ = "teacher_assignments"

    id: Mapped[uuid.UUID] = uuid_pk()
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("teacher_id", "class_id", "subject_id", name="uq_teacher_assignment"),
    )
