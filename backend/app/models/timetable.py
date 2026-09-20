import enum
import uuid
from datetime import time

from sqlalchemy import Enum, ForeignKey, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class Weekday(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"


class TimetableSlot(Base, TenantScopedMixin, TimestampMixin):
    """Un créneau hebdomadaire récurrent (pas de date précise — le même
    créneau se répète chaque semaine de l'année scolaire). La cohérence
    (pas deux matières en même temps pour une classe, pas un enseignant sur
    deux classes en même temps) est vérifiée par le service applicatif à
    l'écriture (voir timetable_service.check_no_overlap), pas par une
    contrainte SQL — plus simple à faire évoluer et à tester explicitement."""

    __tablename__ = "timetable_slots"

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
    day_of_week: Mapped[Weekday] = mapped_column(
        Enum(Weekday, name="weekday", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)
