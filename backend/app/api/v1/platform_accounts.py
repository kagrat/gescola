import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.models.user import User, UserRole
from app.schemas.account import TemporaryPasswordOut
from app.schemas.user import UserOut
from app.services import account_service as accounts

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/tenants/{tenant_id}/users", response_model=list[UserOut])
def list_tenant_users(
    tenant_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> list[UserOut]:
    return list(db.execute(select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)).scalars().all())


@router.post("/tenants/{tenant_id}/users/{user_id}/reset-password", response_model=TemporaryPasswordOut)
def support_reset_password(
    tenant_id: uuid.UUID, user_id: uuid.UUID, response: Response, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> TemporaryPasswordOut:
    """Dépannage par l'éditeur : seule voie pour rouvrir l'accès d'un Fondateur
    bloqué (personne d'autre dans l'établissement ne peut gérer ce compte, et
    l'envoi d'e-mails de réinitialisation n'existe pas encore)."""
    response.headers["Cache-Control"] = "no-store"
    target, temporary = accounts.reset_password(
        db, tenant_id=tenant_id, actor_id=current_user.id, actor_role=UserRole.SUPER_ADMIN, user_id=user_id,
    )
    return TemporaryPasswordOut(user_id=target.id, temporary_password=temporary)
