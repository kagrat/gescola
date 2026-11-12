import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_FINANCE
from app.schemas.academic import StudentOut
from app.schemas.finance import (
    BulkInvoiceReport, BulkInvoiceRequest, FeeDiscountIn, FeePlanApply, FeePlanApplyReport, FeePlanIn, FeePlanOut, FinanceSummary, InvoiceCreate, InvoiceOut, InvoiceRow, PaymentCreate, PaymentOut,
)
from app.services.finance_overview_service import (
    DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, bulk_invoice_class, finance_summary, list_invoice_rows,
)
from app.services import fee_plan_service as plans
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
        id=inv.id, student_id=inv.student_id, label=inv.label, academic_year=inv.academic_year,
        amount_due=float(inv.amount_due),
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
    return record_payment(db, tenant_id=current_user.tenant_id, data=payload, actor_id=current_user.id)


@router.post("/invoices/{invoice_id}/remind")
def remind_invoice_endpoint(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> dict:
    count = send_invoice_reminder(db, tenant_id=current_user.tenant_id, invoice_id=invoice_id, actor_id=current_user.id)
    return {"notified": count}


@router.get("/finance/invoices", response_model=list[InvoiceRow])
def finance_invoices_endpoint(
    response: Response,
    q: str | None = Query(default=None, max_length=100, description="Élève, matricule ou libellé"),
    class_id: uuid.UUID | None = None,
    academic_year: str | None = Query(default=None, pattern=r"^\d{4}-\d{4}$"),
    state: str | None = Query(default=None, description="unpaid | overdue | partially_paid | pending | paid | cancelled"),
    sort: str = Query(default="due", pattern="^(due|balance)$"),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> list[dict]:
    """Toutes les factures de l'établissement, paginées ; total dans X-Total-Count."""
    rows, total = list_invoice_rows(
        db, tenant_id=current_user.tenant_id, q=q, class_id=class_id, academic_year=academic_year,
        state=state, sort=sort, limit=limit, offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/finance/summary", response_model=FinanceSummary)
def finance_summary_endpoint(
    academic_year: str | None = Query(default=None, pattern=r"^\d{4}-\d{4}$"),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> dict:
    return finance_summary(db, tenant_id=current_user.tenant_id, academic_year=academic_year)


@router.post("/finance/bulk-invoices", response_model=BulkInvoiceReport)
def bulk_invoices_endpoint(
    payload: BulkInvoiceRequest,
    dry_run: bool = Query(default=True, description="true = aperçu sans rien créer (défaut)"),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> BulkInvoiceReport:
    return bulk_invoice_class(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, data=payload, commit=not dry_run,
    )


# ---------------- Barème de frais (CP-01) ----------------

@router.get("/finance/fee-plans", response_model=list[FeePlanOut])
def list_fee_plans_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
):
    return plans.list_plans(db, tenant_id=current_user.tenant_id)


@router.post("/finance/fee-plans", response_model=FeePlanOut, status_code=201)
def create_fee_plan_endpoint(
    payload: FeePlanIn, db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
):
    return plans.create_plan(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, data=payload)


@router.put("/finance/fee-plans/{plan_id}", response_model=FeePlanOut)
def update_fee_plan_endpoint(
    plan_id: uuid.UUID, payload: FeePlanIn, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
):
    return plans.update_plan(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, plan_id=plan_id, data=payload)


@router.delete("/finance/fee-plans/{plan_id}", status_code=204)
def delete_fee_plan_endpoint(
    plan_id: uuid.UUID, db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> None:
    plans.delete_plan(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, plan_id=plan_id)


@router.post("/finance/fee-plans/{plan_id}/apply", response_model=FeePlanApplyReport)
def apply_fee_plan_endpoint(
    plan_id: uuid.UUID, payload: FeePlanApply,
    dry_run: bool = Query(default=True, description="true = aperçu sans rien créer (défaut)"),
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
):
    return plans.apply_plan(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, plan_id=plan_id, data=payload, commit=not dry_run)


@router.put("/students/{student_id}/fee-discount", response_model=StudentOut)
def set_fee_discount_endpoint(
    student_id: uuid.UUID, payload: FeeDiscountIn, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
):
    return plans.set_discount(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, student_id=student_id,
                              percent=payload.percent, reason=payload.reason)
