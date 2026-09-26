from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_ACT_AS_DIRECTION
from app.services.reporting_service import overview_report

router = APIRouter(tags=["reports"])


@router.get("/reports/overview")
def overview_report_endpoint(
    term: str | None = None,
    db: Session = Depends(get_tenant_db),
    # Restreint à la direction (+ fondateur) : ce rapport agrège finances +
    # notes + présences, trois domaines dont aucun autre rôle n'a
    # individuellement une vue complète.
    current_user: CurrentUser = Depends(require_roles(*CAN_ACT_AS_DIRECTION)),
) -> dict:
    return overview_report(db, tenant_id=current_user.tenant_id, term=term)
