import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_TEACHING, CAN_READ_REGISTRY
from sqlalchemy import select
from pydantic import BaseModel
from app.models.user import User, UserRole
from app.schemas.teaching import TeacherAssignmentCreate, TeacherAssignmentOut
from app.services.teaching_service import create_assignment, delete_assignment, list_assignments

router = APIRouter(tags=["teaching"])


@router.post("/teacher-assignments", response_model=TeacherAssignmentOut, status_code=201)
def create_assignment_endpoint(
    payload: TeacherAssignmentCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_TEACHING)),
) -> TeacherAssignmentOut:
    return create_assignment(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/teacher-assignments", response_model=list[TeacherAssignmentOut])
def list_assignments_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[TeacherAssignmentOut]:
    return list_assignments(db, tenant_id=current_user.tenant_id)


@router.delete("/teacher-assignments/{assignment_id}", status_code=204)
def delete_assignment_endpoint(
    assignment_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_TEACHING)),
) -> None:
    delete_assignment(db, tenant_id=current_user.tenant_id, assignment_id=assignment_id)


class TeacherOut(BaseModel):
    id: uuid.UUID
    full_name: str


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_TEACHING)),
) -> list[TeacherOut]:
    """Liste légère des enseignants (identifiant + nom) pour la coordination
    pédagogique. Existe parce que /users est réservé à la Direction/Fondateur :
    sans ce point d'entrée, le Censeur — qui gère pourtant les affectations et
    l'emploi du temps — n'avait aucun moyen de choisir un enseignant."""
    rows = db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id, User.role == UserRole.TEACHER, User.is_active.is_(True))
        .order_by(User.full_name)
    ).scalars().all()
    return [TeacherOut(id=u.id, full_name=u.full_name) for u in rows]
