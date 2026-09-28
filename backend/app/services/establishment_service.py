import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.establishment import EstablishmentSettingsUpdate

_BOOLEAN_FIELDS = (
    "bulletin_show_appreciations", "bulletin_show_school_life", "bulletin_show_head_teacher_signature",
)


def get_settings(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    return tenant


# Signataires du bulletin : rôles admis pour chaque désignation.
_SIGNER_ROLES = {
    "bulletin_director_user_id": ((UserRole.SCHOOL_ADMIN, UserRole.FOUNDER), "la Direction ou le Fondateur"),
    "bulletin_censor_user_id": ((UserRole.CENSOR,), "un Censeur"),
}


def _check_signer(db: Session, tenant_id: uuid.UUID, field: str, user_id: uuid.UUID) -> None:
    roles, label = _SIGNER_ROLES[field]
    user = db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable dans cet établissement.")
    if user.role not in roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Le signataire doit être {label}.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce compte est désactivé.")


def update_settings(db: Session, *, tenant_id: uuid.UUID, data: EstablishmentSettingsUpdate) -> Tenant:
    tenant = get_settings(db, tenant_id)
    # mode="json" : les dates des périodes deviennent des chaînes ISO, stockables en JSONB.
    for field, value in data.model_dump(mode="json", exclude_unset=True).items():
        if field in _BOOLEAN_FIELDS and value is None:
            continue  # colonne non nulle : un null explicite est ignoré, pas une erreur
        if field in _SIGNER_ROLES:
            if value is not None:
                value = uuid.UUID(value)
                _check_signer(db, tenant_id, field, value)
            # value None : la désignation est retirée, on revient au choix automatique
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant
