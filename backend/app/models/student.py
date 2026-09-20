import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class StudentStatus(str, enum.Enum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    GRADUATED = "graduated"
    ARCHIVED = "archived"


class Student(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = uuid_pk()
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )

    guardian_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, name="student_status", values_callable=lambda x: [e.value for e in x]),
        default=StudentStatus.ACTIVE, nullable=False,
    )
