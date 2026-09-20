import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class Attendance(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "attendances"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    justified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = ()
