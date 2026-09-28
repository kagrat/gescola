import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_USERS
from app.schemas.account import TemporaryPasswordOut, UserUpdate
from app.schemas.user import UserCreate, UserOut
from app.services import account_service as accounts
from app.services.user_service import create_user, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=201)
def create(
    payload: UserCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> UserOut:
    return create_user(db, tenant_id=current_user.tenant_id, actor_role=current_user.role, data=payload)


@router.get("", response_model=list[UserOut])
def list_all(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> list[UserOut]:
    return list_users(db, tenant_id=current_user.tenant_id)


@router.patch("/{user_id}", response_model=UserOut)
def update(
    user_id: uuid.UUID, payload: UserUpdate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> UserOut:
    return accounts.update_user(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, user_id=user_id, data=payload,
    )


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate(
    user_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> UserOut:
    return accounts.set_active(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, user_id=user_id, active=False,
    )


@router.post("/{user_id}/reactivate", response_model=UserOut)
def reactivate(
    user_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> UserOut:
    return accounts.set_active(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, user_id=user_id, active=True,
    )


@router.post("/{user_id}/reset-password", response_model=TemporaryPasswordOut)
def reset_password(
    user_id: uuid.UUID, response: Response, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> TemporaryPasswordOut:
    response.headers["Cache-Control"] = "no-store"  # la réponse contient un secret
    target, temporary = accounts.reset_password(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, user_id=user_id,
    )
    return TemporaryPasswordOut(user_id=target.id, temporary_password=temporary)


@router.post("/{user_id}/reset-mfa", response_model=UserOut)
def reset_mfa(
    user_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_USERS)),
) -> UserOut:
    return accounts.reset_mfa(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, user_id=user_id,
    )
