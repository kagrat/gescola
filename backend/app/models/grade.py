import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class Grade(Base, TenantScopedMixin, TimestampMixin):
    """Une note ponctuelle. La moyenne (par matière / générale / par période)
    est calculée à la volée par app/services/grade_service.py — jamais stockée
    dénormalisée, pour éviter toute divergence après correction d'une note."""

    __tablename__ = "grades"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    term: Mapped[str] = mapped_column(String(20), nullable=False)  # ex: "T1", "T2", "T3"
    evaluation_label: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "Devoir 1"
    value: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)  # note sur 20
    coefficient: Mapped[float] = mapped_column(Numeric(4, 2), default=1, nullable=False)

    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
