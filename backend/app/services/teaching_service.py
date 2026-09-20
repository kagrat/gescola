import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Subject
from app.models.teaching import TeacherAssignment
from app.models.user import User, UserRole
from app.schemas.teaching import TeacherAssignmentCreate


def create_assignment(db: Session, *, tenant_id: uuid.UUID, data: TeacherAssignmentCreate) -> TeacherAssignment:
    teacher = db.execute(
        select(User).where(User.id == data.teacher_id, User.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enseignant introuvable.")
    if teacher.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce compte n'a pas le rôle Enseignant.")

    school_class = db.execute(
        select(SchoolClass).where(SchoolClass.id == data.class_id, SchoolClass.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable.")

    subject = db.execute(
        select(Subject).where(Subject.id == data.subject_id, Subject.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matière introuvable.")

    assignment = TeacherAssignment(
        tenant_id=tenant_id, teacher_id=data.teacher_id, class_id=data.class_id, subject_id=data.subject_id,
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette affectation existe déjà.")
    db.refresh(assignment)
    return assignment


def list_assignments(db: Session, *, tenant_id: uuid.UUID) -> list[TeacherAssignment]:
    return list(db.execute(select(TeacherAssignment).where(TeacherAssignment.tenant_id == tenant_id)).scalars().all())


def delete_assignment(db: Session, *, tenant_id: uuid.UUID, assignment_id: uuid.UUID) -> None:
    assignment = db.execute(
        select(TeacherAssignment).where(TeacherAssignment.id == assignment_id, TeacherAssignment.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affectation introuvable.")
    db.delete(assignment)
    db.commit()


def teacher_has_any_assignment(db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID) -> bool:
    return db.execute(
        select(TeacherAssignment).where(TeacherAssignment.tenant_id == tenant_id, TeacherAssignment.teacher_id == teacher_id)
    ).first() is not None


def is_teacher_assigned(db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID, class_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
    return db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tenant_id, TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.class_id == class_id, TeacherAssignment.subject_id == subject_id,
        )
    ).first() is not None
