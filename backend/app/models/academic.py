import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class SchoolCycle(str, enum.Enum):
    MATERNELLE = "maternelle"
    PRIMAIRE = "primaire"
    SECONDAIRE = "secondaire"


class SchoolClass(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "school_classes"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "6ème A"
    level: Mapped[str] = mapped_column(String(50), nullable=False)  # ex: "6ème", "CM2"
    cycle: Mapped[SchoolCycle] = mapped_column(
        Enum(SchoolCycle, name="school_cycle", values_callable=lambda x: [e.value for e in x]),
        default=SchoolCycle.PRIMAIRE, nullable=False,
    )
    # Professeur principal de la classe (facultatif). Il rédige l'appréciation
    # générale des bulletins de sa classe et, si l'établissement le souhaite,
    # signe le bulletin.
    head_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Subject(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "Mathématiques"
    default_coefficient: Mapped[float] = mapped_column(Numeric(4, 2), default=1, nullable=False)
