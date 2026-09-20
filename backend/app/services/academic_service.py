import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Subject
from app.models.student import Student
from app.schemas.academic import SchoolClassCreate, StudentCreate, SubjectCreate


def create_class(db: Session, *, tenant_id: uuid.UUID, data: SchoolClassCreate) -> SchoolClass:
    obj = SchoolClass(tenant_id=tenant_id, name=data.name, level=data.level, cycle=data.cycle)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_classes(db: Session, *, tenant_id: uuid.UUID) -> list[SchoolClass]:
    return list(db.execute(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id)).scalars().all())


def create_subject(db: Session, *, tenant_id: uuid.UUID, data: SubjectCreate) -> Subject:
    obj = Subject(tenant_id=tenant_id, name=data.name, default_coefficient=data.default_coefficient)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_subjects(db: Session, *, tenant_id: uuid.UUID) -> list[Subject]:
    return list(db.execute(select(Subject).where(Subject.tenant_id == tenant_id)).scalars().all())


def _get_class_or_404(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
    obj = db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable.")
    return obj


def create_student(db: Session, *, tenant_id: uuid.UUID, data: StudentCreate) -> Student:
    if data.class_id is not None:
        _get_class_or_404(db, tenant_id=tenant_id, class_id=data.class_id)  # empêche le rattachement inter-tenant

    obj = Student(
        tenant_id=tenant_id,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        class_id=data.class_id,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
        guardian_email=data.guardian_email,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_students(db: Session, *, tenant_id: uuid.UUID) -> list[Student]:
    return list(db.execute(select(Student).where(Student.tenant_id == tenant_id)).scalars().all())


def get_student_or_404(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    obj = db.execute(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if obj is None:
        # 404 (pas 403) : ne jamais confirmer l'existence d'une ressource
        # d'un autre établissement.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Élève introuvable.")
    return obj
