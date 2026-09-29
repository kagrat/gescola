import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_ATTENDANCE
from app.schemas.grade import (
    AttendanceCreate, AttendanceOut, AttendanceUpdate, BulkAttendanceCreate, RosterAttendanceOut,
)
from app.services.attendance_service import (
    bulk_mark_attendance, create_attendance, get_class_attendance_for_date, list_attendance, update_attendance,
)

router = APIRouter(tags=["attendance"])


@router.post("/attendance", response_model=AttendanceOut, status_code=201)
def create_attendance_endpoint(
    payload: AttendanceCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> AttendanceOut:
    # Idempotent : appeler deux fois pour le même élève et la même date corrige
    # l'enregistrement (upsert), il ne le double jamais — voir attendance_service.
    return create_attendance(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, data=payload)


@router.patch("/attendance/{attendance_id}", response_model=AttendanceOut)
def update_attendance_endpoint(
    attendance_id: uuid.UUID,
    payload: AttendanceUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> AttendanceOut:
    return update_attendance(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role,
        attendance_id=attendance_id, data=payload,
    )


@router.post("/attendance/bulk", response_model=list[AttendanceOut], status_code=201)
def bulk_attendance_endpoint(
    payload: BulkAttendanceCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> list[AttendanceOut]:
    return bulk_mark_attendance(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, data=payload)


@router.get("/classes/{class_id}/attendance", response_model=list[RosterAttendanceOut])
def class_attendance_endpoint(
    class_id: uuid.UUID,
    date: date,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> list[RosterAttendanceOut]:
    return get_class_attendance_for_date(db, tenant_id=current_user.tenant_id, class_id=class_id, date=date)


@router.get("/students/{student_id}/attendance", response_model=list[AttendanceOut])
def list_attendance_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_ATTENDANCE)),
) -> list[AttendanceOut]:
    return list_attendance(db, tenant_id=current_user.tenant_id, student_id=student_id)
