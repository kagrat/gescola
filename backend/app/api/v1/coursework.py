import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_COURSEWORK, CAN_READ_COURSEWORK
from app.models.user import UserRole
from app.schemas.coursework import (
    HomeworkCreate, HomeworkOut, HomeworkUpdate, LessonLogEntryCreate, LessonLogEntryOut, LessonLogEntryUpdate,
)
from app.services.coursework_service import (
    create_homework, create_lesson_log_entry, list_homework_for_child, list_homework_for_class,
    list_lesson_log_for_class, update_homework, update_lesson_log_entry,
)

router = APIRouter(tags=["coursework"])


# ---------------- Cahier de texte ----------------

@router.post("/lesson-log", response_model=LessonLogEntryOut, status_code=201)
def create_lesson_log_entry_endpoint(
    payload: LessonLogEntryCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_COURSEWORK)),
) -> LessonLogEntryOut:
    return create_lesson_log_entry(
        db, tenant_id=current_user.tenant_id, teacher_id=current_user.id, actor_role=current_user.role, data=payload,
    )


@router.get("/classes/{class_id}/lesson-log", response_model=list[LessonLogEntryOut])
def list_lesson_log_endpoint(
    class_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_COURSEWORK)),
) -> list[LessonLogEntryOut]:
    return list_lesson_log_for_class(db, tenant_id=current_user.tenant_id, class_id=class_id)


@router.patch("/lesson-log/{entry_id}", response_model=LessonLogEntryOut)
def update_lesson_log_entry_endpoint(
    entry_id: uuid.UUID, payload: LessonLogEntryUpdate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_COURSEWORK)),
) -> LessonLogEntryOut:
    return update_lesson_log_entry(
        db, tenant_id=current_user.tenant_id, entry_id=entry_id, actor_role=current_user.role,
        actor_id=current_user.id, data=payload,
    )


# ---------------- Devoirs ----------------

@router.post("/homework", response_model=HomeworkOut, status_code=201)
def create_homework_endpoint(
    payload: HomeworkCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_COURSEWORK)),
) -> HomeworkOut:
    return create_homework(
        db, tenant_id=current_user.tenant_id, teacher_id=current_user.id, actor_role=current_user.role, data=payload,
    )


@router.get("/classes/{class_id}/homework", response_model=list[HomeworkOut])
def list_homework_endpoint(
    class_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_COURSEWORK)),
) -> list[HomeworkOut]:
    return list_homework_for_class(db, tenant_id=current_user.tenant_id, class_id=class_id)


@router.patch("/homework/{homework_id}", response_model=HomeworkOut)
def update_homework_endpoint(
    homework_id: uuid.UUID, payload: HomeworkUpdate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_COURSEWORK)),
) -> HomeworkOut:
    return update_homework(
        db, tenant_id=current_user.tenant_id, homework_id=homework_id, actor_role=current_user.role,
        actor_id=current_user.id, data=payload,
    )


@router.get("/children/{student_id}/homework", response_model=list[HomeworkOut])
def list_homework_for_child_endpoint(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[HomeworkOut]:
    return list_homework_for_child(
        db, tenant_id=current_user.tenant_id, parent_user_id=current_user.id, student_id=student_id,
    )
