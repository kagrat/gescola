"""
Facturation plateforme : GESCOLA facture les établissements pour l'usage du
logiciel. À ne pas confondre avec app/models/finance.py, qui gère la
facturation école → parents (frais de scolarité).

Modèle inspiré des pratiques standards des SaaS B2B (Stripe Billing, Chargebee
et équivalents) : plans tarifaires, abonnement par établissement avec période
d'essai, factures générées par période, paiements enregistrés manuellement
(aucune passerelle de paiement réelle n'est intégrée — voir README).
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, uuid_pk


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"      # période d'essai en cours
    ACTIVE = "active"          # abonnement payant à jour
    PAST_DUE = "past_due"      # facture en retard, accès encore toléré (grâce)
    SUSPENDED = "suspended"    # accès bloqué pour impayé
    CANCELED = "canceled"      # résilié


class PlatformInvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PlatformPaymentMethod(str, enum.Enum):
    MOBILE_MONEY = "mobile_money"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"


class PlatformPlan(Base, TimestampMixin):
    """Une offre tarifaire GESCOLA (ex: 'Starter', 'Pro'). Non tenant-scoped :
    les plans sont globaux à la plateforme, gérés par le Super Admin."""

    __tablename__ = "platform_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    price_per_month: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_students: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = illimité
    is_default_trial_plan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subscription(Base, TimestampMixin):
    """Abonnement d'UN établissement à UN plan. Un seul abonnement actif par
    tenant (contrainte d'unicité sur tenant_id) — changer de plan met à jour
    la ligne existante plutôt que d'en créer une nouvelle, pour toujours avoir
    un état courant simple à vérifier (voir platform_access_service)."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionStatus.TRIALING, nullable=False,
    )
    trial_ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["PlatformPlan"] = relationship()


class PlatformInvoice(Base, TimestampMixin):
    """Facture GESCOLA → établissement pour une période donnée."""

    __tablename__ = "platform_invoices"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PlatformInvoiceStatus] = mapped_column(
        Enum(PlatformInvoiceStatus, name="platform_invoice_status", values_callable=lambda x: [e.value for e in x]),
        default=PlatformInvoiceStatus.PENDING, nullable=False,
    )

    payments: Mapped[list["PlatformPayment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class PlatformPayment(Base, TimestampMixin):
    """Paiement enregistré manuellement par le Super Admin (aucune passerelle
    mobile money réelle intégrée — voir README, section limites)."""

    __tablename__ = "platform_payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[PlatformPaymentMethod] = mapped_column(
        Enum(PlatformPaymentMethod, name="platform_payment_method", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    invoice: Mapped["PlatformInvoice"] = relationship(back_populates="payments")
