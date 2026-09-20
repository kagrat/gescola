import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_TEACHING, CAN_READ_REGISTRY
from app.models.user import UserRole
from app.schemas.timetable import TimetableSlotCreate, TimetableSlotOut
from app.services.timetable_service import create_slot, delete_slot, list_class_timetable, list_teacher_timetable

router = APIRouter(tags=["timetable"])


@router.post("/timetable", response_model=TimetableSlotOut, status_code=201)
def create_slot_endpoint(
    payload: TimetableSlotCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_TEACHING)),
) -> TimetableSlotOut:
    return create_slot(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/classes/{class_id}/timetable", response_model=list[TimetableSlotOut])
def get_class_timetable_endpoint(
    class_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[TimetableSlotOut]:
    return list_class_timetable(db, tenant_id=current_user.tenant_id, class_id=class_id)


@router.get("/users/me/timetable", response_model=list[TimetableSlotOut])
def get_my_timetable_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(UserRole.TEACHER)),
) -> list[TimetableSlotOut]:
    return list_teacher_timetable(db, tenant_id=current_user.tenant_id, teacher_id=current_user.id)


@router.delete("/timetable/{slot_id}", status_code=204)
def delete_slot_endpoint(
    slot_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_TEACHING)),
) -> None:
    delete_slot(db, tenant_id=current_user.tenant_id, slot_id=slot_id)
