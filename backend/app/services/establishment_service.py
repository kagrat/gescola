import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.schemas.establishment import EstablishmentSettingsUpdate

_BOOLEAN_FIELDS = (
    "bulletin_show_appreciations", "bulletin_show_school_life", "bulletin_show_head_teacher_signature",
)


def get_settings(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    return tenant


def update_settings(db: Session, *, tenant_id: uuid.UUID, data: EstablishmentSettingsUpdate) -> Tenant:
    tenant = get_settings(db, tenant_id)
    # mode="json" : les dates des périodes deviennent des chaînes ISO, stockables en JSONB.
    for field, value in data.model_dump(mode="json", exclude_unset=True).items():
        if field in _BOOLEAN_FIELDS and value is None:
            continue  # colonne non nulle : un null explicite est ignoré, pas une erreur
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant
