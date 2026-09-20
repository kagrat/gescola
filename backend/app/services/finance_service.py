import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Invoice, InvoiceStatus, Payment
from app.schemas.finance import InvoiceCreate, InvoiceOut, PaymentCreate
from app.services.academic_service import get_student_or_404


def create_invoice(db: Session, *, tenant_id: uuid.UUID, data: InvoiceCreate) -> Invoice:
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)
    obj = Invoice(
        tenant_id=tenant_id, student_id=data.student_id, label=data.label,
        amount_due=data.amount_due, due_date=data.due_date,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _to_out(invoice: Invoice) -> InvoiceOut:
    paid = sum(float(p.amount) for p in invoice.payments)
    return InvoiceOut(
        id=invoice.id, student_id=invoice.student_id, label=invoice.label,
        amount_due=float(invoice.amount_due), due_date=invoice.due_date, status=invoice.status,
        amount_paid=paid, balance=round(float(invoice.amount_due) - paid, 2),
    )


def list_invoices(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[InvoiceOut]:
    get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    invoices = db.execute(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.student_id == student_id)
    ).scalars().all()
    return [_to_out(inv) for inv in invoices]


def record_payment(db: Session, *, tenant_id: uuid.UUID, data: PaymentCreate) -> Payment:
    invoice = db.execute(
        select(Invoice).where(Invoice.id == data.invoice_id, Invoice.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facture introuvable.")
    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette facture est annulée.")

    payment = Payment(
        tenant_id=tenant_id, invoice_id=invoice.id, amount=data.amount,
        method=data.method, reference=data.reference,
    )
    db.add(payment)
    db.flush()
    db.refresh(invoice)  # recharge la relation payments pour inclure ce nouveau paiement

    total_paid = sum(float(p.amount) for p in invoice.payments)
    if total_paid >= float(invoice.amount_due):
        invoice.status = InvoiceStatus.PAID
    elif total_paid > 0:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    db.commit()
    db.refresh(payment)
    return payment
