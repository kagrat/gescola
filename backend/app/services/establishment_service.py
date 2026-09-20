import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.schemas.establishment import EstablishmentSettingsUpdate


def get_settings(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    return tenant


def update_settings(db: Session, *, tenant_id: uuid.UUID, data: EstablishmentSettingsUpdate) -> Tenant:
    tenant = get_settings(db, tenant_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant
