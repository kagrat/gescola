import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import Subject
from app.models.grade import Grade
from app.schemas.academic import StudentCreate  # noqa: F401  (import conservé pour cohérence de module)
from app.schemas.grade import GradeCreate, StudentAverageOut
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action


def create_grade(db: Session, *, tenant_id: uuid.UUID, teacher_id: uuid.UUID, data: GradeCreate) -> Grade:
    # Vérifie que l'élève appartient bien au même établissement (lève 404 sinon).
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)

    subject = db.execute(
        select(Subject).where(Subject.id == data.subject_id, Subject.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matière introuvable.")

    grade = Grade(
        tenant_id=tenant_id,
        student_id=data.student_id,
        subject_id=data.subject_id,
        teacher_id=teacher_id,
        term=data.term,
        evaluation_label=data.evaluation_label,
        value=data.value,
        coefficient=data.coefficient,
    )
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade


def list_grades(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID, term: str | None = None) -> list[Grade]:
    get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    stmt = select(Grade).where(Grade.tenant_id == tenant_id, Grade.student_id == student_id)
    if term:
        stmt = stmt.where(Grade.term == term)
    return list(db.execute(stmt).scalars().all())


def lock_term_grades(
    db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID, term: str, actor_id: uuid.UUID
) -> int:
    """Verrouille toutes les notes d'un élève pour une période donnée (validation
    direction). Retourne le nombre de notes verrouillées. Action journalisée."""
    grades = list_grades(db, tenant_id=tenant_id, student_id=student_id, term=term)
    now = datetime.now(timezone.utc)
    count = 0
    for g in grades:
        if not g.is_locked:
            g.is_locked = True
            g.locked_at = now
            g.locked_by = actor_id
            count += 1
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="grade.lock_term",
        target_type="Student", target_id=str(student_id), metadata={"term": term, "count": count},
    )
    db.commit()
    return count


def update_grade(
    db: Session, *, tenant_id: uuid.UUID, grade_id: uuid.UUID, actor_id: uuid.UUID, is_admin_override: bool,
    new_value: float,
) -> Grade:
    grade = db.execute(
        select(Grade).where(Grade.id == grade_id, Grade.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if grade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note introuvable.")

    if grade.is_locked and not is_admin_override:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette note est verrouillée après validation ; seule la direction peut la modifier.",
        )

    old_value = grade.value
    grade.value = new_value

    if grade.is_locked and is_admin_override:
        # Modification exceptionnelle d'une note déjà validée : traçabilité
        # renforcée obligatoire (section 7.5 / risque "modification frauduleuse").
        log_action(
            db, tenant_id=tenant_id, actor_user_id=actor_id, action="grade.override_after_lock",
            target_type="Grade", target_id=str(grade.id),
            metadata={"old_value": float(old_value), "new_value": float(new_value)},
        )

    db.commit()
    db.refresh(grade)
    return grade


def compute_student_average(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID, term: str) -> StudentAverageOut:
    grades = list_grades(db, tenant_id=tenant_id, student_id=student_id, term=term)

    by_subject: dict[uuid.UUID, list[Grade]] = defaultdict(list)
    for g in grades:
        by_subject[g.subject_id].append(g)

    subject_averages: dict[str, float] = {}
    weighted_sum = 0.0
    weight_total = 0.0

    for subject_id, subject_grades in by_subject.items():
        s_weighted = sum(float(g.value) * float(g.coefficient) for g in subject_grades)
        s_weight = sum(float(g.coefficient) for g in subject_grades)
        if s_weight == 0:
            continue
        subject_avg = round(s_weighted / s_weight, 2)
        subject_averages[str(subject_id)] = subject_avg
        # La moyenne générale pondère chaque matière par la somme de ses coefficients.
        weighted_sum += subject_avg * s_weight
        weight_total += s_weight

    general_average = round(weighted_sum / weight_total, 2) if weight_total else 0.0

    return StudentAverageOut(
        student_id=student_id, term=term, subject_averages=subject_averages, general_average=general_average
    )
