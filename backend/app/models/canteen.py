import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class CanteenSubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class CanteenPlan(Base, TenantScopedMixin, TimestampMixin):
    """Formule de cantine (ex: '5 jours/semaine', 'Ponctuel'), propre à
    chaque établissement — le prix varie fortement d'une école à l'autre."""

    __tablename__ = "canteen_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_per_month: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class CanteenSubscription(Base, TenantScopedMixin, TimestampMixin):
    """Abonnement d'un élève à une formule pour un mois donné. À la création,
    une facture correspondante est générée automatiquement dans le module
    finance (voir canteen_service.subscribe) — un seul point d'entrée pour
    la facturation, pas deux systèmes de facturation parallèles."""

    __tablename__ = "canteen_subscriptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canteen_plans.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # format "YYYY-MM"
    status: Mapped[CanteenSubscriptionStatus] = mapped_column(
        Enum(CanteenSubscriptionStatus, name="canteen_subscription_status", values_callable=lambda x: [e.value for e in x]),
        default=CanteenSubscriptionStatus.ACTIVE, nullable=False,
    )
