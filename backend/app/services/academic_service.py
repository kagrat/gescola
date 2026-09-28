import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Subject
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.academic import SchoolClassCreate, SchoolClassUpdate, StudentCreate, StudentUpdate, SubjectCreate, SubjectUpdate


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


def update_subject(db: Session, *, tenant_id: uuid.UUID, subject_id: uuid.UUID, data: SubjectUpdate) -> Subject:
    subject = db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matière introuvable.")
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(subject, field, value)
    db.commit()
    db.refresh(subject)
    return subject


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
        matricule=_clean_matricule(data.matricule),
        gender=data.gender,
        is_repeater=data.is_repeater,
        class_id=data.class_id,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
        guardian_email=data.guardian_email,
    )
    db.add(obj)
    _commit_or_duplicate_matricule(db)
    db.refresh(obj)
    return obj


def _clean_matricule(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _commit_or_duplicate_matricule(db: Session) -> None:
    """Le matricule est unique par établissement (index partiel) : une
    violation devient un 409 explicite plutôt qu'une erreur serveur."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce matricule est déjà utilisé dans l'établissement.")


def list_students(db: Session, *, tenant_id: uuid.UUID) -> list[Student]:
    return list(db.execute(select(Student).where(Student.tenant_id == tenant_id)).scalars().all())


def update_student(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID, data: StudentUpdate) -> Student:
    student = get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    updates = data.model_dump(exclude_unset=True)
    if "class_id" in updates and updates["class_id"] is not None:
        _get_class_or_404(db, tenant_id=tenant_id, class_id=updates["class_id"])  # empêche le rattachement inter-tenant
    if "matricule" in updates:
        updates["matricule"] = _clean_matricule(updates["matricule"])
    for field, value in updates.items():
        setattr(student, field, value)
    _commit_or_duplicate_matricule(db)
    db.refresh(student)
    return student


def update_class(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, data: SchoolClassUpdate) -> SchoolClass:
    school_class = _get_class_or_404(db, tenant_id=tenant_id, class_id=class_id)
    updates = data.model_dump(exclude_unset=True)
    head_id = updates.get("head_teacher_id")
    if head_id is not None:
        teacher = db.execute(
            select(User).where(User.id == head_id, User.tenant_id == tenant_id, User.role == UserRole.TEACHER)
        ).scalar_one_or_none()
        if teacher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enseignant introuvable.")
    for field, value in updates.items():
        setattr(school_class, field, value)
    db.commit()
    db.refresh(school_class)
    return school_class


def get_student_or_404(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    obj = db.execute(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if obj is None:
        # 404 (pas 403) : ne jamais confirmer l'existence d'une ressource
        # d'un autre établissement.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Élève introuvable.")
    return obj
