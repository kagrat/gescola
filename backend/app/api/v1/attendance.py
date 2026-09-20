import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_ATTENDANCE
from app.schemas.grade import AttendanceCreate, AttendanceOut
from app.services.attendance_service import create_attendance, list_attendance

router = APIRouter(tags=["attendance"])


@router.post("/attendance", response_model=AttendanceOut, status_code=201)
def create_attendance_endpoint(
    payload: AttendanceCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> AttendanceOut:
    return create_attendance(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/students/{student_id}/attendance", response_model=list[AttendanceOut])
def list_attendance_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> list[AttendanceOut]:
    return list_attendance(db, tenant_id=current_user.tenant_id, student_id=student_id)
