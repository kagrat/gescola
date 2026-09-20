import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canteen import CanteenPlan, CanteenSubscription
from app.models.finance import Invoice
from app.schemas.canteen import CanteenPlanCreate, CanteenSubscriptionCreate
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action


def create_plan(db: Session, *, tenant_id: uuid.UUID, data: CanteenPlanCreate) -> CanteenPlan:
    plan = CanteenPlan(tenant_id=tenant_id, name=data.name, price_per_month=data.price_per_month)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def list_plans(db: Session, *, tenant_id: uuid.UUID) -> list[CanteenPlan]:
    return list(db.execute(select(CanteenPlan).where(CanteenPlan.tenant_id == tenant_id)).scalars().all())


def subscribe(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, data: CanteenSubscriptionCreate) -> CanteenSubscription:
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)

    plan = db.execute(
        select(CanteenPlan).where(CanteenPlan.id == data.plan_id, CanteenPlan.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formule de cantine introuvable.")

    existing = db.execute(
        select(CanteenSubscription).where(
            CanteenSubscription.tenant_id == tenant_id, CanteenSubscription.student_id == data.student_id,
            CanteenSubscription.month == data.month,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un abonnement existe déjà pour ce mois.")

    # Un seul point d'entrée pour la facturation : on crée une facture standard
    # (module finance) plutôt qu'un système de facturation cantine séparé.
    invoice = Invoice(
        tenant_id=tenant_id, student_id=data.student_id, label=f"Cantine — {plan.name} — {data.month}",
        amount_due=plan.price_per_month, due_date=date.fromisoformat(f"{data.month}-05"),
    )
    db.add(invoice)
    db.flush()

    subscription = CanteenSubscription(
        tenant_id=tenant_id, student_id=data.student_id, plan_id=plan.id, invoice_id=invoice.id, month=data.month,
    )
    db.add(subscription)
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="canteen.subscribe",
               target_type="CanteenSubscription", target_id=None,
               metadata={"student_id": str(data.student_id), "month": data.month})
    db.commit()
    db.refresh(subscription)
    return subscription


def list_subscriptions(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[CanteenSubscription]:
    get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    return list(
        db.execute(
            select(CanteenSubscription).where(
                CanteenSubscription.tenant_id == tenant_id, CanteenSubscription.student_id == student_id
            )
        ).scalars().all()
    )
