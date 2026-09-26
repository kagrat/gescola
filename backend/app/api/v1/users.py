from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_USERS
from app.schemas.user import UserCreate, UserOut
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
