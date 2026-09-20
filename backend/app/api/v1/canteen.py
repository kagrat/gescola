import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_FINANCE
from app.schemas.canteen import (
    CanteenPlanCreate, CanteenPlanOut, CanteenSubscriptionCreate, CanteenSubscriptionOut,
)
from app.services.canteen_service import create_plan, list_plans, list_subscriptions, subscribe

router = APIRouter(prefix="/canteen", tags=["canteen"])


@router.post("/plans", response_model=CanteenPlanOut, status_code=201)
def create_plan_endpoint(
    payload: CanteenPlanCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> CanteenPlanOut:
    return create_plan(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/plans", response_model=list[CanteenPlanOut])
def list_plans_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> list[CanteenPlanOut]:
    return list_plans(db, tenant_id=current_user.tenant_id)


@router.post("/subscriptions", response_model=CanteenSubscriptionOut, status_code=201)
def subscribe_endpoint(
    payload: CanteenSubscriptionCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> CanteenSubscriptionOut:
    return subscribe(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, data=payload)


@router.get("/students/{student_id}/subscriptions", response_model=list[CanteenSubscriptionOut])
def list_subscriptions_endpoint(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> list[CanteenSubscriptionOut]:
    return list_subscriptions(db, tenant_id=current_user.tenant_id, student_id=student_id)
