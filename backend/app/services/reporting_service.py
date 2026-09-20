import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import Attendance, AttendanceStatus
from app.models.academic import SchoolClass
from app.models.finance import Invoice, InvoiceStatus, Payment
from app.models.grade import Grade
from app.models.student import Student, StudentStatus


def overview_report(db: Session, *, tenant_id: uuid.UUID, term: str | None = None) -> dict:
    """Indicateurs agrégés pour le tableau de bord de direction. Toutes les
    requêtes restent filtrées par tenant_id explicitement (défense en
    profondeur, cohérent avec le reste du code — RLS reste la deuxième
    barrière, pas la seule)."""

    total_students = db.execute(
        select(func.count()).select_from(Student).where(Student.tenant_id == tenant_id, Student.status == StudentStatus.ACTIVE)
    ).scalar_one()

    # --- Finances : encaissé vs. dû sur les factures non annulées ---
    amount_due_total = db.execute(
        select(func.coalesce(func.sum(Invoice.amount_due), 0)).where(
            Invoice.tenant_id == tenant_id, Invoice.status != InvoiceStatus.CANCELLED
        )
    ).scalar_one()
    amount_paid_total = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Payment.tenant_id == tenant_id, Invoice.status != InvoiceStatus.CANCELLED)
    ).scalar_one()

    # --- Présences : taux d'absentéisme non justifié sur les 30 derniers jours enregistrés ---
    attendance_rows = db.execute(
        select(Attendance.status, Attendance.justified).where(Attendance.tenant_id == tenant_id)
    ).all()
    total_attendance = len(attendance_rows)
    unjustified_absences = sum(1 for status, justified in attendance_rows if status == AttendanceStatus.ABSENT and not justified)
    attendance_rate = (
        round(100 * (1 - sum(1 for s, _ in attendance_rows if s == AttendanceStatus.ABSENT) / total_attendance), 1)
        if total_attendance else None
    )

    # --- Notes : moyenne générale par classe, pour la période demandée ---
    grade_query = select(Grade.student_id, Grade.value, Grade.coefficient).where(Grade.tenant_id == tenant_id)
    if term:
        grade_query = grade_query.where(Grade.term == term)
    grade_rows = db.execute(grade_query).all()

    student_class = dict(
        db.execute(select(Student.id, Student.class_id).where(Student.tenant_id == tenant_id)).all()
    )
    class_names = dict(
        db.execute(select(SchoolClass.id, SchoolClass.name).where(SchoolClass.tenant_id == tenant_id)).all()
    )

    per_class_weighted: dict[str, float] = defaultdict(float)
    per_class_weight: dict[str, float] = defaultdict(float)
    for student_id, value, coefficient in grade_rows:
        class_id = student_class.get(student_id)
        key = class_names.get(class_id, "Sans classe") if class_id else "Sans classe"
        per_class_weighted[key] += float(value) * float(coefficient)
        per_class_weight[key] += float(coefficient)

    average_by_class = {
        name: round(per_class_weighted[name] / per_class_weight[name], 2)
        for name in per_class_weighted if per_class_weight[name] > 0
    }

    return {
        "total_active_students": total_students,
        "finance": {
            "amount_due_total": float(amount_due_total),
            "amount_paid_total": float(amount_paid_total),
            "outstanding_total": float(amount_due_total) - float(amount_paid_total),
        },
        "attendance": {
            "records_count": total_attendance,
            "unjustified_absences": unjustified_absences,
            "attendance_rate_percent": attendance_rate,
        },
        "average_by_class": average_by_class,
    }
