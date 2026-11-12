import enum
import uuid
from datetime import date

from sqlalchemy import Index, Date, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    MOBILE_MONEY = "mobile_money"  # intégration passerelle réelle hors périmètre de ce livrable — voir README
    BANK_TRANSFER = "bank_transfer"


class Invoice(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (Index("ix_invoices_tenant_year", "tenant_id", "academic_year"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)  # ex: "Scolarité T1 2026-2027"
    # Année scolaire à laquelle se rattache la facture (rapports : « dû de l'année » vs « arriérés »).
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", values_callable=lambda x: [e.value for e in x]),
        default=InvoiceStatus.PENDING, nullable=False,
    )

    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("tenant_id", "receipt_number", name="uq_payment_receipt_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ex: réf. transaction mobile money
    # Numéro de reçu : suite continue par établissement (jamais réutilisée, sans trou en usage normal).
    receipt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")


class FeePlan(Base, TenantScopedMixin, TimestampMixin):
    """Barème de frais d'un niveau (ex. « Scolarité » en 6ème : 3 tranches).

    Réutilisable d'une année à l'autre : les tranches portent un MOIS et un JOUR
    d'échéance, l'année est déduite de l'année scolaire facturée (septembre à
    décembre = année de début, janvier à août = année de fin). Les factures
    créées sont indépendantes du barème : le modifier ne touche pas à l'existant."""

    __tablename__ = "fee_plans"
    __table_args__ = (UniqueConstraint("tenant_id", "level", "name", name="uq_fee_plan_level_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # [{"label": "Tranche 1", "amount": 50000, "month": 10, "day": 15}, ...] dans l'ordre chronologique scolaire
    installments: Mapped[list] = mapped_column(JSONB, nullable=False)
