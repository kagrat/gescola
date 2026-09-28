import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class ReportCardStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class SubjectAppreciation(Base, TenantScopedMixin, TimestampMixin):
    """Appréciation d'un enseignant sur un élève, pour une matière et une
    période — imprimée dans la colonne « Appréciation du professeur » du
    bulletin. Une seule par (élève, matière, période)."""

    __tablename__ = "subject_appreciations"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(10), nullable=False)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(300), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "subject_id", "term", name="uq_subject_appreciation"),)


class ReportCard(Base, TenantScopedMixin, TimestampMixin):
    """Bulletin d'un élève pour une période.

    `snapshot` fige les CHIFFRES (moyennes, rangs, vie scolaire, appréciations
    de matière, signataires) au moment de la génération/publication : un
    bulletin publié ne change plus, même si une note est corrigée ensuite.
    Les réglages d'affichage (sections visibles) et les images (logo,
    signatures, tampons) sont en revanche lus au moment de l'impression : voir
    bulletin_pdf et le README (limites)."""

    __tablename__ = "report_cards"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term: Mapped[str] = mapped_column(String(10), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    status: Mapped[ReportCardStatus] = mapped_column(
        Enum(ReportCardStatus, name="report_card_status", values_callable=lambda x: [e.value for e in x]),
        default=ReportCardStatus.DRAFT, nullable=False,
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    principal_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    council_decision: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (UniqueConstraint("student_id", "term", "academic_year", name="uq_report_card_student_term"),)
