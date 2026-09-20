import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
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

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)  # ex: "Scolarité T1 2026-2027"
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", values_callable=lambda x: [e.value for e in x]),
        default=InvoiceStatus.PENDING, nullable=False,
    )

    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ex: réf. transaction mobile money

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
