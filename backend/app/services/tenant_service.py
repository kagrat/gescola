from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.schemas.user import TenantCreate


def create_tenant(db: Session, data: TenantCreate) -> Tenant:
    existing = db.execute(select(Tenant).where(Tenant.code == data.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce code établissement existe déjà.")
    tenant = Tenant(name=data.name, code=data.code)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def list_tenants(db: Session) -> list[Tenant]:
    return list(db.execute(select(Tenant)).scalars().all())
