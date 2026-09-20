import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.billing import (
    PlatformInvoice, PlatformInvoiceStatus, PlatformPayment, PlatformPaymentMethod, PlatformPlan, Subscription,
    SubscriptionStatus,
)
from app.schemas.billing import PlatformPlanCreate, SubscriptionUpdate

DEFAULT_TRIAL_DAYS = 14


def effective_status(sub: Subscription) -> SubscriptionStatus:
    """Le statut « réel » d'un abonnement, en tenant compte de la date du
    jour — un essai expiré sans passage à un plan payant est traité comme
    suspendu, sans nécessiter de tâche planifiée (cron) pour le constater :
    le calcul se fait à la lecture, chaque fois que c'est nécessaire."""
    if sub.status == SubscriptionStatus.TRIALING and sub.trial_ends_at and sub.trial_ends_at < date.today():
        return SubscriptionStatus.SUSPENDED
    return sub.status


def check_tenant_access(db: Session, tenant_id: uuid.UUID) -> None:
    """Lève 402 Payment Required si l'établissement est suspendu ou résilié.

    Un établissement SANS ligne d'abonnement n'est pas restreint : c'est le
    cas des tenants créés manuellement par le Super Admin hors du flux de
    facturation (ex: établissements pilotes historiques) — le suivi de
    facturation est une fonctionnalité additive, pas une contrainte
    rétroactive sur les établissements déjà en place.
    """
    sub = db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id)).scalar_one_or_none()
    if sub is None:
        return
    if effective_status(sub) in (SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELED):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Accès suspendu : l'abonnement de cet établissement n'est pas à jour. Contactez l'éditeur.",
        )


# --- Plans (Super Admin) ---

def create_plan(db: Session, data: PlatformPlanCreate) -> PlatformPlan:
    existing = db.execute(select(PlatformPlan).where(PlatformPlan.code == data.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce code de plan existe déjà.")
    plan = PlatformPlan(
        name=data.name, code=data.code, price_per_month=data.price_per_month,
        max_students=data.max_students, is_default_trial_plan=data.is_default_trial_plan,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def list_plans(db: Session) -> list[PlatformPlan]:
    return list(db.execute(select(PlatformPlan).where(PlatformPlan.is_active.is_(True))).scalars().all())


def get_default_trial_plan(db: Session) -> PlatformPlan:
    plan = db.execute(
        select(PlatformPlan).where(PlatformPlan.is_default_trial_plan.is_(True), PlatformPlan.is_active.is_(True))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Aucun plan d'essai par défaut n'est configuré. Contactez l'administrateur de la plateforme.",
        )
    return plan


# --- Abonnements ---

def start_trial_subscription(db: Session, *, tenant_id: uuid.UUID, plan: PlatformPlan | None = None) -> Subscription:
    """Crée l'abonnement d'essai d'un nouvel établissement. Appelé une seule
    fois, à la création du tenant (inscription en libre-service ou création
    manuelle par le Super Admin)."""
    plan = plan or get_default_trial_plan(db)
    sub = Subscription(
        tenant_id=tenant_id, plan_id=plan.id, status=SubscriptionStatus.TRIALING,
        trial_ends_at=date.today() + timedelta(days=DEFAULT_TRIAL_DAYS),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def get_subscription_for_tenant(db: Session, tenant_id: uuid.UUID) -> Subscription:
    sub = db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id)).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun abonnement pour cet établissement.")
    return sub


def update_subscription(db: Session, *, tenant_id: uuid.UUID, data: SubscriptionUpdate) -> Subscription:
    sub = get_subscription_for_tenant(db, tenant_id)
    if data.plan_id is not None:
        plan = db.get(PlatformPlan, data.plan_id)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan introuvable.")
        sub.plan_id = plan.id
    if data.status is not None:
        sub.status = data.status
        if data.status == SubscriptionStatus.ACTIVE:
            sub.suspended_at = None
    db.commit()
    db.refresh(sub)
    return sub


# --- Factures et paiements ---

@dataclass
class InvoiceView:
    invoice: PlatformInvoice
    amount_paid: float
    balance: float


def _to_view(invoice: PlatformInvoice) -> InvoiceView:
    paid = sum(float(p.amount) for p in invoice.payments)
    return InvoiceView(invoice=invoice, amount_paid=paid, balance=round(float(invoice.amount_due) - paid, 2))


def generate_invoice(db: Session, *, tenant_id: uuid.UUID) -> PlatformInvoice:
    """Génère la facture du mois courant pour un établissement, à partir du
    prix de son plan. Action manuelle déclenchée par le Super Admin dans ce
    livrable (pas de tâche planifiée automatique — voir README)."""
    sub = get_subscription_for_tenant(db, tenant_id)
    period_start = date.today().replace(day=1)
    period_end = period_start + relativedelta(months=1) - timedelta(days=1)

    existing = db.execute(
        select(PlatformInvoice).where(
            PlatformInvoice.tenant_id == tenant_id, PlatformInvoice.period_start == period_start
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une facture existe déjà pour cette période.")

    invoice = PlatformInvoice(
        tenant_id=tenant_id, subscription_id=sub.id, period_start=period_start, period_end=period_end,
        amount_due=sub.plan.price_per_month, due_date=period_end,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def list_invoices(db: Session, *, tenant_id: uuid.UUID) -> list[InvoiceView]:
    invoices = db.execute(
        select(PlatformInvoice).where(PlatformInvoice.tenant_id == tenant_id).order_by(PlatformInvoice.period_start.desc())
    ).scalars().all()
    return [_to_view(inv) for inv in invoices]


def record_payment(
    db: Session, *, actor_id: uuid.UUID, invoice_id: uuid.UUID, amount: float,
    method: PlatformPaymentMethod, reference: str | None,
) -> PlatformPayment:
    invoice = db.get(PlatformInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facture introuvable.")
    if invoice.status == PlatformInvoiceStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette facture est annulée.")

    payment = PlatformPayment(invoice_id=invoice.id, amount=amount, method=method, reference=reference, recorded_by=actor_id)
    db.add(payment)
    db.flush()
    db.refresh(invoice)

    total_paid = sum(float(p.amount) for p in invoice.payments)
    if total_paid >= float(invoice.amount_due):
        invoice.status = PlatformInvoiceStatus.PAID
        # Un paiement complet lève automatiquement une suspension pour impayé.
        sub = db.get(Subscription, invoice.subscription_id)
        if sub and sub.status in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.SUSPENDED):
            sub.status = SubscriptionStatus.ACTIVE
            sub.suspended_at = None

    db.commit()
    db.refresh(payment)
    return payment
