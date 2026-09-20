import enum
import uuid

from sqlalchemy import Enum, Numeric, String
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


class Subject(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "Mathématiques"
    default_coefficient: Mapped[float] = mapped_column(Numeric(4, 2), default=1, nullable=False)
