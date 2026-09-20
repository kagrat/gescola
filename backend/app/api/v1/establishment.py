from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.models.user import UserRole
from app.schemas.establishment import EstablishmentSettingsOut, EstablishmentSettingsUpdate
from app.services.establishment_service import get_settings, update_settings

router = APIRouter(prefix="/establishment", tags=["establishment"])

# Accessible en lecture à tout le personnel de l'établissement (utile pour
# afficher le logo/l'en-tête sur les documents qu'ils consultent) ; modifiable
# uniquement par la Direction.
READ_ROLES = (
    UserRole.SCHOOL_ADMIN, UserRole.CENSOR, UserRole.SUPERVISOR, UserRole.ACCOUNTANT, UserRole.STAFF, UserRole.TEACHER,
)


@router.get("/settings", response_model=EstablishmentSettingsOut)
def get_settings_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*READ_ROLES)),
) -> EstablishmentSettingsOut:
    return get_settings(db, current_user.tenant_id)


@router.patch("/settings", response_model=EstablishmentSettingsOut)
def update_settings_endpoint(
    payload: EstablishmentSettingsUpdate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.SCHOOL_ADMIN)),
) -> EstablishmentSettingsOut:
    return update_settings(db, tenant_id=current_user.tenant_id, data=payload)
