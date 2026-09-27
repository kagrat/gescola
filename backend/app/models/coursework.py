import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class LessonLogEntry(Base, TenantScopedMixin, TimestampMixin):
    """Cahier de texte : ce qui a été fait en classe, séance par séance —
    contenu du cours et avancement dans le programme. Distinct de l'emploi
    du temps (qui dit QUAND un cours a lieu) et des notes (qui évaluent
    l'élève) : ce document répond à « qu'est-ce qui a été enseigné ? »,
    souvent contrôlé par l'inspection pédagogique.

    Restriction d'écriture identique aux notes (voir grade_service) : un
    enseignant ayant au moins une affectation enregistrée ne peut renseigner
    le cahier de texte que pour ses classes/matières assignées."""

    __tablename__ = "lesson_log_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # ce qui a été fait / avancement dans le programme


class Homework(Base, TenantScopedMixin, TimestampMixin):
    """Un devoir donné à une classe pour une matière, avec échéance. Visible
    par les parents des élèves de la classe concernée (pas de remise en
    ligne : GESCOLA n'a pas de compte élève, voir README) — sert à informer,
    pas à collecter des rendus."""

    __tablename__ = "homework"

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
