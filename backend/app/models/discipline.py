import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class IncidentCategory(str, enum.Enum):
    BEHAVIOR = "behavior"                # comportement perturbateur, insolence
    VIOLENCE = "violence"                # bagarre, violence verbale ou physique
    PROPERTY_DAMAGE = "property_damage"  # dégradation de matériel
    CHEATING = "cheating"                # triche, fraude
    REPEATED_LATENESS = "repeated_lateness"
    OTHER = "other"


class IncidentSeverity(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SERIOUS = "serious"


class IncidentStatus(str, enum.Enum):
    REPORTED = "reported"          # signalé, pas encore pris en charge
    UNDER_REVIEW = "under_review"  # pris en charge par la vie scolaire / le censeur
    RESOLVED = "resolved"          # clos


class SanctionType(str, enum.Enum):
    WARNING = "warning"                        # avertissement
    DETENTION = "detention"                    # retenue
    EXTRA_WORK = "extra_work"                  # travail supplémentaire
    PARENT_SUMMON = "parent_summon"            # convocation des parents
    TEMPORARY_EXCLUSION = "temporary_exclusion"  # exclusion temporaire
    OTHER = "other"


def _enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda x: [e.value for e in x])


class Incident(Base, TenantScopedMixin, TimestampMixin):
    """Un incident de vie scolaire signalé par un membre du personnel.

    Distinct du simple statut de présence (absent/retard) : un incident est un
    fait disciplinaire décrit en texte libre (comportement, bagarre,
    dégradation…), avec une gravité et un cycle de traitement. Les sanctions
    ne sont jamais posées par celui qui signale (surveillant, enseignant) :
    elles relèvent du censeur, de la direction ou du fondateur."""

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[IncidentCategory] = mapped_column(_enum(IncidentCategory, "incident_category"), nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(_enum(IncidentSeverity, "incident_severity"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        _enum(IncidentStatus, "incident_status"), default=IncidentStatus.REPORTED, nullable=False
    )

    sanctions: Mapped[list["Sanction"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="Sanction.created_at"
    )


class Sanction(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "sanctions"

    id: Mapped[uuid.UUID] = uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    imposed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sanction_type: Mapped[SanctionType] = mapped_column(_enum(SanctionType, "sanction_type"), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="sanctions")
