import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class EnrollmentOutcome(str, enum.Enum):
    PROMOTED = "promoted"    # passe dans la classe supérieure
    REPEATED = "repeated"    # redouble : reste dans la même classe
    GRADUATED = "graduated"  # termine le cursus de l'établissement


class StudentEnrollment(Base, TenantScopedMixin, TimestampMixin):
    """Parcours d'un élève : une ligne par année scolaire CLÔTURÉE.

    Écrite uniquement par le passage d'année. Les noms de classes sont copiés
    (instantané) : renommer ou supprimer une classe plus tard ne doit jamais
    réécrire l'historique d'un élève (base des attestations et relevés)."""

    __tablename__ = "student_enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_year", name="uq_enrollment_student_year"),
        Index("ix_enrollments_tenant_year", "tenant_id", "academic_year"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[EnrollmentOutcome] = mapped_column(
        Enum(EnrollmentOutcome, name="enrollment_outcome", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    next_class_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
