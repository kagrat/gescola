import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Subject
from app.models.timetable import TimetableSlot
from app.models.user import User, UserRole
from app.schemas.timetable import TimetableSlotCreate


def _ranges_overlap(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def _check_no_overlap(db: Session, *, tenant_id: uuid.UUID, data: TimetableSlotCreate, exclude_id: uuid.UUID | None = None) -> None:
    """Un cours ne peut pas chevaucher, le meme jour : un autre cours de la
    MEME CLASSE (deux matieres en meme temps), ni un autre cours du MEME
    ENSEIGNANT (sur une autre classe). Verifie explicitement plutot que de
    compter sur une contrainte SQL, pour un message d'erreur clair."""
    same_day = select(TimetableSlot).where(
        TimetableSlot.tenant_id == tenant_id, TimetableSlot.day_of_week == data.day_of_week,
    )
    if exclude_id:
        same_day = same_day.where(TimetableSlot.id != exclude_id)

    existing_slots = db.execute(same_day).scalars().all()
    for slot in existing_slots:
        if not _ranges_overlap(data.start_time, data.end_time, slot.start_time, slot.end_time):
            continue
        if slot.class_id == data.class_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette classe a déjà un cours sur ce créneau (conflit d'emploi du temps).",
            )
        if slot.teacher_id == data.teacher_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet enseignant a déjà un cours sur ce créneau, dans une autre classe.",
            )


def create_slot(db: Session, *, tenant_id: uuid.UUID, data: TimetableSlotCreate) -> TimetableSlot:
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

    teacher = db.execute(
        select(User).where(User.id == data.teacher_id, User.tenant_id == tenant_id, User.role == UserRole.TEACHER)
    ).scalar_one_or_none()
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enseignant introuvable.")

    _check_no_overlap(db, tenant_id=tenant_id, data=data)

    slot = TimetableSlot(
        tenant_id=tenant_id, class_id=data.class_id, subject_id=data.subject_id, teacher_id=data.teacher_id,
        day_of_week=data.day_of_week, start_time=data.start_time, end_time=data.end_time, room=data.room,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def list_class_timetable(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID) -> list[TimetableSlot]:
    return list(
        db.execute(
            select(TimetableSlot).where(TimetableSlot.tenant_id == tenant_id, TimetableSlot.class_id == class_id)
        ).scalars().all()
    )


def list_teacher_timetable(db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID) -> list[TimetableSlot]:
    return list(
        db.execute(
            select(TimetableSlot).where(TimetableSlot.tenant_id == tenant_id, TimetableSlot.teacher_id == teacher_id)
        ).scalars().all()
    )


def delete_slot(db: Session, *, tenant_id: uuid.UUID, slot_id: uuid.UUID) -> None:
    slot = db.execute(
        select(TimetableSlot).where(TimetableSlot.id == slot_id, TimetableSlot.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Créneau introuvable.")
    db.delete(slot)
    db.commit()
