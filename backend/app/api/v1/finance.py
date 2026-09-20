import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_FINANCE
from app.schemas.finance import InvoiceCreate, InvoiceOut, PaymentCreate, PaymentOut
from app.services.finance_service import create_invoice, list_invoices, record_payment
from app.services.notification_service import send_invoice_reminder

router = APIRouter(tags=["finance"])


@router.post("/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice_endpoint(
    payload: InvoiceCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> InvoiceOut:
    inv = create_invoice(db, tenant_id=current_user.tenant_id, data=payload)
    return InvoiceOut(
        id=inv.id, student_id=inv.student_id, label=inv.label, amount_due=float(inv.amount_due),
        due_date=inv.due_date, status=inv.status, amount_paid=0, balance=float(inv.amount_due),
    )


@router.get("/students/{student_id}/invoices", response_model=list[InvoiceOut])
def list_invoices_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> list[InvoiceOut]:
    return list_invoices(db, tenant_id=current_user.tenant_id, student_id=student_id)


@router.post("/payments", response_model=PaymentOut, status_code=201)
def record_payment_endpoint(
    payload: PaymentCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> PaymentOut:
    return record_payment(db, tenant_id=current_user.tenant_id, data=payload)


@router.post("/invoices/{invoice_id}/remind")
def remind_invoice_endpoint(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> dict:
    count = send_invoice_reminder(db, tenant_id=current_user.tenant_id, invoice_id=invoice_id, actor_id=current_user.id)
    return {"notified": count}
