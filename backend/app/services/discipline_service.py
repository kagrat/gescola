import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.discipline import Incident, IncidentStatus, Sanction
from app.models.user import UserRole
from app.schemas.discipline import IncidentCreate, SanctionCreate
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action


def report_incident(db: Session, *, tenant_id: uuid.UUID, reporter_id: uuid.UUID, data: IncidentCreate) -> Incident:
    # 404 si l'élève n'appartient pas à cet établissement.
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)
    incident = Incident(
        tenant_id=tenant_id, student_id=data.student_id, reported_by=reporter_id, occurred_at=data.occurred_at,
        category=data.category, severity=data.severity, description=data.description,
    )
    db.add(incident)
    db.flush()
    log_action(
        db, tenant_id=tenant_id, actor_user_id=reporter_id, action="incident.reported",
        target_type="Incident", target_id=str(incident.id),
        metadata={"student_id": str(data.student_id), "severity": data.severity.value},
    )
    db.commit()
    db.refresh(incident)
    return incident


def list_incidents(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole,
    student_id: uuid.UUID | None = None, incident_status: IncidentStatus | None = None,
) -> list[Incident]:
    query = select(Incident).where(Incident.tenant_id == tenant_id)
    if actor_role == UserRole.TEACHER:
        # Un enseignant ne voit que les incidents qu'il a lui-même signalés :
        # le dossier disciplinaire complet d'un élève ne le concerne pas.
        query = query.where(Incident.reported_by == actor_id)
    if student_id is not None:
        query = query.where(Incident.student_id == student_id)
    if incident_status is not None:
        query = query.where(Incident.status == incident_status)
    return list(db.execute(query.order_by(Incident.occurred_at.desc())).scalars().all())


def _get_incident_or_404(db: Session, *, tenant_id: uuid.UUID, incident_id: uuid.UUID) -> Incident:
    incident = db.execute(
        select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident introuvable.")
    return incident


def update_incident_status(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, incident_id: uuid.UUID, new_status: IncidentStatus,
) -> Incident:
    incident = _get_incident_or_404(db, tenant_id=tenant_id, incident_id=incident_id)
    previous = incident.status
    incident.status = new_status
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="incident.status_changed",
        target_type="Incident", target_id=str(incident.id),
        metadata={"from": previous.value, "to": new_status.value},
    )
    db.commit()
    db.refresh(incident)
    return incident


def add_sanction(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, incident_id: uuid.UUID, data: SanctionCreate,
) -> Incident:
    incident = _get_incident_or_404(db, tenant_id=tenant_id, incident_id=incident_id)
    sanction = Sanction(
        tenant_id=tenant_id, incident_id=incident.id, imposed_by=actor_id, sanction_type=data.sanction_type,
        details=data.details, start_date=data.start_date, end_date=data.end_date,
    )
    db.add(sanction)
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="incident.sanction_imposed",
        target_type="Incident", target_id=str(incident.id), metadata={"sanction_type": data.sanction_type.value},
    )
    db.commit()
    db.refresh(incident)
    return incident
