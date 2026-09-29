"""Présences.

Un seul enregistrement par élève et par jour (contrainte en base) : refaire
l'appel le même jour CORRIGE l'enregistrement existant, il ne le double
jamais. C'est le sens des fonctions d'upsert ci-dessous.

Restriction : un enseignant avec au moins une affectation ne peut prendre ou
corriger la présence que des classes où il enseigne (affectation ou
professeur principal) — même règle que pour les notes et le cahier de texte
(voir teaching_service.teacher_teaches_class). Les autres rôles autorisés
(Direction, Fondateur, Censeur, Surveillant, Secrétariat) ne sont jamais
restreints.
"""
import uuid
from datetime import date as date_type

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass
from app.models.attendance import Attendance, AttendanceStatus
from app.models.student import Student, StudentStatus
from app.models.user import UserRole
from app.schemas.grade import AttendanceCreate, AttendanceUpdate, BulkAttendanceCreate, RosterAttendanceOut
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action
from app.services.teaching_service import teacher_has_any_assignment, teacher_teaches_class


def _check_class_restriction(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, class_id: uuid.UUID | None) -> None:
    if actor_role != UserRole.TEACHER:
        return
    if not teacher_has_any_assignment(db, tenant_id=tenant_id, teacher_id=actor_id):
        return  # pas encore configuré : grandfathering, comme pour les notes
    if class_id is None or not teacher_teaches_class(db, tenant_id=tenant_id, teacher_id=actor_id, class_id=class_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous n'êtes pas affecté à cette classe.")


def _get_class_or_404(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
    school_class = db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable.")
    return school_class


def _upsert(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID, date: date_type, status_value: AttendanceStatus, justified: bool) -> Attendance:
    existing = db.execute(
        select(Attendance).where(Attendance.tenant_id == tenant_id, Attendance.student_id == student_id, Attendance.date == date)
    ).scalar_one_or_none()
    if existing is None:
        existing = Attendance(tenant_id=tenant_id, student_id=student_id, date=date, status=status_value, justified=justified)
        db.add(existing)
    else:
        existing.status = status_value
        existing.justified = justified
    return existing


def create_attendance(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, data: AttendanceCreate) -> Attendance:
    student = get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)
    _check_class_restriction(db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role, class_id=student.class_id)
    obj = _upsert(db, tenant_id=tenant_id, student_id=data.student_id, date=data.date, status_value=data.status, justified=data.justified)
    db.commit()
    db.refresh(obj)
    return obj


def update_attendance(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, attendance_id: uuid.UUID, data: AttendanceUpdate,
) -> Attendance:
    """Corrige un enregistrement après coup (élève oublié à l'appel, absence
    justifiée reçue plus tard…). Une correction qui change le statut est
    journalisée — modifier l'historique des présences est sensible."""
    record = db.execute(
        select(Attendance).where(Attendance.id == attendance_id, Attendance.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enregistrement introuvable.")
    student = db.get(Student, record.student_id)
    _check_class_restriction(db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role, class_id=student.class_id if student else None)

    old_status = record.status
    if data.status is not None and data.status != record.status:
        record.status = data.status
        log_action(
            db, tenant_id=tenant_id, actor_user_id=actor_id, action="attendance.corrected",
            target_type="Attendance", target_id=str(record.id),
            metadata={"student_id": str(record.student_id), "date": record.date.isoformat(), "from": old_status.value, "to": data.status.value},
        )
    if data.justified is not None:
        record.justified = data.justified
    db.commit()
    db.refresh(record)
    return record


def bulk_mark_attendance(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, data: BulkAttendanceCreate,
) -> list[Attendance]:
    """Appel en masse pour une classe entière, un jour donné : une seule
    action plutôt qu'un enregistrement élève par élève."""
    _get_class_or_404(db, tenant_id=tenant_id, class_id=data.class_id)
    _check_class_restriction(db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role, class_id=data.class_id)

    roster_ids = set(
        db.execute(
            select(Student.id).where(Student.tenant_id == tenant_id, Student.class_id == data.class_id)
        ).scalars().all()
    )
    unknown = {e.student_id for e in data.entries} - roster_ids
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un ou plusieurs élèves n'appartiennent pas à cette classe.")

    records = [
        _upsert(db, tenant_id=tenant_id, student_id=e.student_id, date=data.date, status_value=e.status, justified=e.justified)
        for e in data.entries
    ]
    db.commit()
    for r in records:
        db.refresh(r)
    return records


def get_class_attendance_for_date(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, date: date_type) -> list[RosterAttendanceOut]:
    """Le registre complet de la classe pour un jour donné : chaque élève actif,
    avec son statut déjà enregistré ce jour-là, ou aucun (`status: null`) si
    l'appel n'a pas encore été fait — alimente l'écran « Faire l'appel »,
    qu'on l'ouvre pour la première fois ou pour corriger un appel déjà fait."""
    _get_class_or_404(db, tenant_id=tenant_id, class_id=class_id)
    students = db.execute(
        select(Student).where(Student.tenant_id == tenant_id, Student.class_id == class_id, Student.status == StudentStatus.ACTIVE)
        .order_by(Student.last_name, Student.first_name)
    ).scalars().all()
    existing = {
        a.student_id: a
        for a in db.execute(
            select(Attendance).where(Attendance.tenant_id == tenant_id, Attendance.date == date, Attendance.student_id.in_([s.id for s in students]))
        ).scalars().all()
    } if students else {}
    return [
        RosterAttendanceOut(
            student_id=s.id, first_name=s.first_name, last_name=s.last_name,
            attendance_id=(existing[s.id].id if s.id in existing else None),
            status=(existing[s.id].status if s.id in existing else None),
            justified=(existing[s.id].justified if s.id in existing else False),
        )
        for s in students
    ]


def list_attendance(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[Attendance]:
    get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    return list(
        db.execute(
            select(Attendance).where(Attendance.tenant_id == tenant_id, Attendance.student_id == student_id)
            .order_by(Attendance.date.desc())
        ).scalars().all()
    )
