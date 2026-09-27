import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_DISCIPLINE, CAN_READ_INCIDENTS, CAN_REPORT_INCIDENT
from app.models.discipline import IncidentStatus
from app.schemas.discipline import IncidentCreate, IncidentOut, IncidentStatusUpdate, SanctionCreate
from app.services.discipline_service import add_sanction, list_incidents, report_incident, update_incident_status

router = APIRouter(tags=["discipline"])


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def report_incident_endpoint(
    payload: IncidentCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_REPORT_INCIDENT)),
) -> IncidentOut:
    return report_incident(db, tenant_id=current_user.tenant_id, reporter_id=current_user.id, data=payload)


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents_endpoint(
    student_id: uuid.UUID | None = None, status: IncidentStatus | None = None,
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_READ_INCIDENTS)),
) -> list[IncidentOut]:
    return list_incidents(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role,
        student_id=student_id, incident_status=status,
    )


@router.patch("/incidents/{incident_id}/status", response_model=IncidentOut)
def update_status_endpoint(
    incident_id: uuid.UUID, payload: IncidentStatusUpdate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_DISCIPLINE)),
) -> IncidentOut:
    return update_incident_status(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, incident_id=incident_id,
        new_status=payload.status,
    )


@router.post("/incidents/{incident_id}/sanctions", response_model=IncidentOut, status_code=201)
def add_sanction_endpoint(
    incident_id: uuid.UUID, payload: SanctionCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_DISCIPLINE)),
) -> IncidentOut:
    return add_sanction(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, incident_id=incident_id, data=payload,
    )
