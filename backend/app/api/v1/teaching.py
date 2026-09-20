import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_TEACHING, CAN_READ_REGISTRY
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
