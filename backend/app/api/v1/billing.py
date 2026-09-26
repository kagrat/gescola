import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.billing import (
    PlatformInvoiceOut, PlatformPaymentCreate, PlatformPaymentOut, PlatformPlanCreate, PlatformPlanOut,
    SubscriptionOut, SubscriptionUpdate,
)
from app.services.platform_billing_service import (
    check_billing_access, create_plan, effective_status, generate_invoice, get_subscription_for_tenant,
    list_invoices, list_plans, record_payment, start_trial_subscription, update_subscription,
)

router = APIRouter(tags=["platform-billing"])


def _subscription_out(sub) -> SubscriptionOut:
    return SubscriptionOut(
        id=sub.id, tenant_id=sub.tenant_id, plan=PlatformPlanOut.model_validate(sub.plan),
        status=sub.status, effective_status=effective_status(sub),
        trial_ends_at=sub.trial_ends_at, current_period_end=sub.current_period_end,
    )


def _invoice_out(view) -> PlatformInvoiceOut:
    inv = view.invoice
    return PlatformInvoiceOut(
        id=inv.id, tenant_id=inv.tenant_id, period_start=inv.period_start, period_end=inv.period_end,
        amount_due=float(inv.amount_due), due_date=inv.due_date, status=inv.status,
        amount_paid=view.amount_paid, balance=view.balance,
    )


# --- Plans (Super Admin) ---

@router.post("/platform/plans", response_model=PlatformPlanOut, status_code=201)
def create_plan_endpoint(
    payload: PlatformPlanCreate, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> PlatformPlanOut:
    return create_plan(db, payload)


@router.get("/platform/plans", response_model=list[PlatformPlanOut])
def list_plans_endpoint(
    db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> list[PlatformPlanOut]:
    return list_plans(db)


# --- Abonnements et factures d'un établissement (Super Admin) ---

@router.get("/platform/tenants/{tenant_id}/subscription", response_model=SubscriptionOut)
def get_subscription_endpoint(
    tenant_id: uuid.UUID, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> SubscriptionOut:
    return _subscription_out(get_subscription_for_tenant(db, tenant_id))


@router.post("/platform/tenants/{tenant_id}/subscription", response_model=SubscriptionOut, status_code=201)
def start_subscription_endpoint(
    tenant_id: uuid.UUID, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> SubscriptionOut:
    """Démarre un abonnement d'essai pour un établissement créé manuellement
    (POST /tenants) et qui n'en a pas encore — l'inscription en libre-service
    (POST /auth/signup) en crée un automatiquement, ce n'est nécessaire ici
    que pour les établissements créés hors de ce flux."""
    return _subscription_out(start_trial_subscription(db, tenant_id=tenant_id))


@router.patch("/platform/tenants/{tenant_id}/subscription", response_model=SubscriptionOut)
def update_subscription_endpoint(
    tenant_id: uuid.UUID, payload: SubscriptionUpdate, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> SubscriptionOut:
    return _subscription_out(update_subscription(db, tenant_id=tenant_id, data=payload))


@router.post("/platform/tenants/{tenant_id}/invoices/generate", response_model=PlatformInvoiceOut, status_code=201)
def generate_invoice_endpoint(
    tenant_id: uuid.UUID, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> PlatformInvoiceOut:
    inv = generate_invoice(db, tenant_id=tenant_id)
    return PlatformInvoiceOut(
        id=inv.id, tenant_id=inv.tenant_id, period_start=inv.period_start, period_end=inv.period_end,
        amount_due=float(inv.amount_due), due_date=inv.due_date, status=inv.status, amount_paid=0,
        balance=float(inv.amount_due),
    )


@router.get("/platform/tenants/{tenant_id}/invoices", response_model=list[PlatformInvoiceOut])
def list_invoices_endpoint(
    tenant_id: uuid.UUID, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> list[PlatformInvoiceOut]:
    return [_invoice_out(v) for v in list_invoices(db, tenant_id=tenant_id)]


@router.post("/platform/payments", response_model=PlatformPaymentOut, status_code=201)
def record_payment_endpoint(
    payload: PlatformPaymentCreate, db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> PlatformPaymentOut:
    return record_payment(
        db, actor_id=current_user.id, invoice_id=payload.invoice_id, amount=payload.amount,
        method=payload.method, reference=payload.reference,
    )


# --- Consultation par la direction de son propre établissement ---

@router.get("/billing/me", response_model=SubscriptionOut)
def my_subscription_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.FOUNDER)),
) -> SubscriptionOut:
    check_billing_access(db, tenant_id=current_user.tenant_id, actor_role=current_user.role)
    # get_tenant_db a déjà positionné le contexte RLS, mais Subscription
    # n'est pas une table RLS (elle n'a pas besoin d'isolation par tenant_id
    # au niveau base, seulement au niveau filtrage applicatif explicite ici).
    return _subscription_out(get_subscription_for_tenant(db, current_user.tenant_id))


@router.get("/billing/me/invoices", response_model=list[PlatformInvoiceOut])
def my_invoices_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.FOUNDER)),
) -> list[PlatformInvoiceOut]:
    check_billing_access(db, tenant_id=current_user.tenant_id, actor_role=current_user.role)
    return [_invoice_out(v) for v in list_invoices(db, tenant_id=current_user.tenant_id)]
