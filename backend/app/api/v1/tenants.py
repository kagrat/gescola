from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.user import TenantCreate, TenantOut
from app.services.tenant_service import create_tenant, list_tenants

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantOut, status_code=201)
def create(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> TenantOut:
    return create_tenant(db, payload)


@router.get("", response_model=list[TenantOut])
def list_all(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> list[TenantOut]:
    return list_tenants(db)
