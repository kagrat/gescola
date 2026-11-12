"""Barèmes de frais par niveau, tranches et remises élève (CP-01).

Un barème décrit la scolarité d'un niveau en tranches datées. L'appliquer à une
classe crée une facture par élève actif et par tranche, avec la remise de
l'élève (fratrie, bourse…) déjà déduite. Même garanties que la facturation de
classe : aperçu sans écriture, rejouable sans doublon (libellé + année), un seul
lancement à la fois par établissement, journal d'audit."""
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import FeePlan, Invoice, InvoiceStatus
from app.models.student import Student, StudentStatus
from app.schemas.finance import FeePlanApply, FeePlanApplyReport, FeePlanIn, InstallmentReport
from app.services.academic_service import _get_class_or_404, get_student_or_404
from app.services.academic_year_service import current_year, ensure_academic_year, is_valid_year, next_year
from app.services.audit_service import log_action

MAX_STUDENTS = 2000


def due_date_for(year: str, month: int, day: int) -> date:
    """Septembre-décembre : année de début ; janvier-août : année de fin."""
    start = int(year[:4])
    return date(start if month >= 9 else start + 1, month, day)


def _chrono(inst: dict) -> tuple[int, int]:
    return ((inst["month"] - 9) % 12, inst["day"])  # ordre de l'année scolaire : sept → août


def discounted(amount: float, percent: float) -> float:
    """Montant après remise, arrondi au franc (FCFA sans centimes) ; jamais négatif."""
    value = Decimal(str(amount)) * (Decimal(100) - Decimal(str(percent))) / Decimal(100)
    return float(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _out(plan: FeePlan) -> dict:
    return {"id": plan.id, "level": plan.level, "name": plan.name, "installments": plan.installments,
            "total": round(sum(i["amount"] for i in plan.installments), 2)}


def list_plans(db: Session, *, tenant_id: uuid.UUID) -> list[dict]:
    plans = db.execute(select(FeePlan).where(FeePlan.tenant_id == tenant_id).order_by(FeePlan.level, FeePlan.name)).scalars()
    return [_out(p) for p in plans]


def _get_plan(db: Session, tenant_id: uuid.UUID, plan_id: uuid.UUID) -> FeePlan:
    plan = db.execute(select(FeePlan).where(FeePlan.id == plan_id, FeePlan.tenant_id == tenant_id)).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Barème introuvable.")
    return plan


def _installments(data: FeePlanIn) -> list[dict]:
    items = sorted((i.model_dump() for i in data.installments), key=_chrono)
    return items


def create_plan(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, data: FeePlanIn) -> dict:
    plan = FeePlan(tenant_id=tenant_id, level=data.level, name=data.name, installments=_installments(data))
    db.add(plan)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Un barème de ce nom existe déjà pour ce niveau.")
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="fee_plan.created", target_type="FeePlan", target_id=str(plan.id),
               metadata={"level": plan.level, "name": plan.name, "total": _out(plan)["total"]})
    db.commit()
    db.refresh(plan)
    return _out(plan)


def update_plan(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, plan_id: uuid.UUID, data: FeePlanIn) -> dict:
    plan = _get_plan(db, tenant_id, plan_id)
    plan.level, plan.name, plan.installments = data.level, data.name, _installments(data)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Un barème de ce nom existe déjà pour ce niveau.")
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="fee_plan.updated", target_type="FeePlan", target_id=str(plan.id),
               metadata={"level": plan.level, "name": plan.name, "total": _out(plan)["total"]})
    db.commit()
    db.refresh(plan)
    return _out(plan)


def delete_plan(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, plan_id: uuid.UUID) -> None:
    plan = _get_plan(db, tenant_id, plan_id)
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="fee_plan.deleted", target_type="FeePlan", target_id=str(plan.id),
               metadata={"level": plan.level, "name": plan.name})
    db.delete(plan)  # les factures déjà créées restent : elles ne dépendent pas du barème
    db.commit()


def set_discount(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, student_id: uuid.UUID, percent: float, reason: str | None) -> Student:
    student = get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    before = float(student.fee_discount_percent)
    student.fee_discount_percent = round(percent, 2)
    student.fee_discount_reason = (reason or "").strip() or None if percent > 0 else None
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="student.fee_discount_set", target_type="Student", target_id=str(student_id),
               metadata={"from": before, "to": float(percent), "reason": student.fee_discount_reason})
    db.commit()
    db.refresh(student)
    return student


def apply_plan(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, plan_id: uuid.UUID, data: FeePlanApply, commit: bool) -> FeePlanApplyReport:
    plan = _get_plan(db, tenant_id, plan_id)
    school_class = _get_class_or_404(db, tenant_id=tenant_id, class_id=data.class_id)
    if school_class.level.strip().lower() != plan.level.strip().lower():
        raise HTTPException(status_code=422, detail=f"Ce barème est prévu pour le niveau « {plan.level} », pas « {school_class.level} ».")
    if commit:
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"bulk-invoice:{tenant_id}"})  # même verrou que la facturation de classe
    current = ensure_academic_year(db, tenant_id) if commit else current_year(db, tenant_id)
    year = data.academic_year or current
    if not is_valid_year(year) or year > next_year(current):
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Année scolaire invalide pour une facture (au plus {next_year(current)}).")

    students = list(db.execute(
        select(Student).where(Student.tenant_id == tenant_id, Student.class_id == data.class_id, Student.status == StudentStatus.ACTIVE)
        .order_by(Student.id)
    ).scalars())
    if not students:
        db.rollback()
        raise HTTPException(status_code=409, detail="Aucun élève actif dans cette classe.")
    if len(students) > MAX_STUDENTS:
        db.rollback()
        raise HTTPException(status_code=413, detail=f"Classe trop grande pour une facturation en une fois (maximum {MAX_STUDENTS}).")

    ids = [s.id for s in students]
    reports: list[InstallmentReport] = []
    grand_total = 0.0
    for inst in plan.installments:
        label = f"{plan.name} – {inst['label']}"
        due = due_date_for(year, inst["month"], inst["day"])
        already = set(db.execute(select(Invoice.student_id).where(
            Invoice.tenant_id == tenant_id, Invoice.student_id.in_(ids), Invoice.academic_year == year,
            func.lower(Invoice.label) == label.lower(), Invoice.status != InvoiceStatus.CANCELLED,
        )).scalars())
        new_invoices, total = [], 0.0
        for s in students:
            if s.id in already:
                continue
            amount = discounted(inst["amount"], float(s.fee_discount_percent))
            if amount <= 0:
                continue  # remise de 100 % : rien à facturer
            new_invoices.append(Invoice(tenant_id=tenant_id, student_id=s.id, label=label, academic_year=year, amount_due=amount, due_date=due))
            total += amount
        if commit:
            db.add_all(new_invoices)
        grand_total += total
        reports.append(InstallmentReport(label=label, due_date=due, created=len(new_invoices), already_billed=len(already), total_amount=round(total, 2)))

    created = sum(r.created for r in reports)
    if commit and created:
        log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="fee_plan.applied", target_type="SchoolClass", target_id=str(data.class_id),
                   metadata={"plan": plan.name, "academic_year": year, "created": created, "total": round(grand_total, 2)})
    if commit:
        db.commit()
    return FeePlanApplyReport(
        dry_run=not commit, class_name=school_class.name, academic_year=year, students=len(students),
        discounted_students=sum(1 for s in students if float(s.fee_discount_percent) > 0),
        exempted_students=sum(1 for s in students if float(s.fee_discount_percent) >= 100),
        installments=reports, total_amount=round(grand_total, 2),
    )
