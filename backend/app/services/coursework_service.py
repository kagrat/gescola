import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Subject
from app.models.coursework import Homework, LessonLogEntry
from app.models.student import Student
from app.models.user import UserRole
from app.schemas.coursework import (
    HomeworkCreate, HomeworkUpdate, LessonLogEntryCreate, LessonLogEntryUpdate,
)
from app.services.guardian_service import assert_parent_linked_to_student
from app.services.teaching_service import is_teacher_assigned, teacher_has_any_assignment


def _check_class_subject_or_404(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, subject_id: uuid.UUID) -> None:
    school_class = db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable.")
    subject = db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matière introuvable.")


def _check_assignment_restriction(
    db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID, actor_role: UserRole,
    class_id: uuid.UUID, subject_id: uuid.UUID,
) -> None:
    """Même règle que pour les notes (voir grade_service) : un enseignant
    avec au moins une affectation ne peut agir que sur ses classes/matières
    assignées. La Direction et le Fondateur ne sont jamais restreints."""
    if actor_role != UserRole.TEACHER:
        return
    if not teacher_has_any_assignment(db, tenant_id=tenant_id, teacher_id=teacher_id):
        return
    if not is_teacher_assigned(db, tenant_id=tenant_id, teacher_id=teacher_id, class_id=class_id, subject_id=subject_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas affecté à cette classe pour cette matière.",
        )


# ---------------- Cahier de texte ----------------

def create_lesson_log_entry(
    db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID, actor_role: UserRole, data: LessonLogEntryCreate,
) -> LessonLogEntry:
    _check_class_subject_or_404(db, tenant_id=tenant_id, class_id=data.class_id, subject_id=data.subject_id)
    _check_assignment_restriction(
        db, tenant_id=tenant_id, teacher_id=teacher_id, actor_role=actor_role,
        class_id=data.class_id, subject_id=data.subject_id,
    )
    entry = LessonLogEntry(
        tenant_id=tenant_id, class_id=data.class_id, subject_id=data.subject_id, teacher_id=teacher_id,
        session_date=data.session_date, content=data.content,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_lesson_log_for_class(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID) -> list[LessonLogEntry]:
    return list(
        db.execute(
            select(LessonLogEntry)
            .where(LessonLogEntry.tenant_id == tenant_id, LessonLogEntry.class_id == class_id)
            .order_by(LessonLogEntry.session_date.desc())
        ).scalars().all()
    )


def update_lesson_log_entry(
    db: Session, *, tenant_id: uuid.UUID, entry_id: uuid.UUID, actor_role: UserRole, actor_id: uuid.UUID,
    data: LessonLogEntryUpdate,
) -> LessonLogEntry:
    entry = db.execute(
        select(LessonLogEntry).where(LessonLogEntry.id == entry_id, LessonLogEntry.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrée introuvable.")
    if actor_role == UserRole.TEACHER and entry.teacher_id != actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez modifier que vos propres entrées.",
        )
    entry.content = data.content
    db.commit()
    db.refresh(entry)
    return entry


# ---------------- Devoirs ----------------

def create_homework(
    db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID, actor_role: UserRole, data: HomeworkCreate,
) -> Homework:
    _check_class_subject_or_404(db, tenant_id=tenant_id, class_id=data.class_id, subject_id=data.subject_id)
    _check_assignment_restriction(
        db, tenant_id=tenant_id, teacher_id=teacher_id, actor_role=actor_role,
        class_id=data.class_id, subject_id=data.subject_id,
    )
    hw = Homework(
        tenant_id=tenant_id, class_id=data.class_id, subject_id=data.subject_id, teacher_id=teacher_id,
        title=data.title, description=data.description, due_date=data.due_date,
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return hw


def list_homework_for_class(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID) -> list[Homework]:
    return list(
        db.execute(
            select(Homework).where(Homework.tenant_id == tenant_id, Homework.class_id == class_id)
            .order_by(Homework.due_date.asc())
        ).scalars().all()
    )


def update_homework(
    db: Session, *, tenant_id: uuid.UUID, homework_id: uuid.UUID, actor_role: UserRole, actor_id: uuid.UUID,
    data: HomeworkUpdate,
) -> Homework:
    hw = db.execute(
        select(Homework).where(Homework.id == homework_id, Homework.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if hw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Devoir introuvable.")
    if actor_role == UserRole.TEACHER and hw.teacher_id != actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez modifier que vos propres devoirs.",
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hw, field, value)
    db.commit()
    db.refresh(hw)
    return hw


def list_homework_for_child(db: Session, *, tenant_id: uuid.UUID, parent_user_id: uuid.UUID, student_id: uuid.UUID) -> list[Homework]:
    assert_parent_linked_to_student(db, tenant_id=tenant_id, parent_user_id=parent_user_id, student_id=student_id)
    student = db.execute(select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)).scalar_one_or_none()
    if student is None or student.class_id is None:
        return []
    return list_homework_for_class(db, tenant_id=tenant_id, class_id=student.class_id)
