"""Vue financière de l'établissement (AU-09) : liste des factures, synthèse,
facturation d'une classe entière.

Le statut d'une facture est **calculé à la lecture** (soldée / échue / partielle
/ en attente) à partir du solde et de l'échéance : le champ `status` stocké ne
passe jamais à « échue » tout seul (il n'y a pas de tâche planifiée), donc s'y
fier ferait oublier les impayés. Les factures annulées sont exclues des
totaux ; les soldes sont calculés en base (somme des paiements), pas en Python.
"""
import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass
from app.models.finance import Invoice, InvoiceStatus, Payment
from app.models.student import Student, StudentStatus
from app.schemas.finance import BulkInvoiceReport, BulkInvoiceRequest
from app.services.academic_service import _get_class_or_404
from app.services.academic_year_service import current_year, ensure_academic_year, is_valid_year, next_year
from app.services.audit_service import log_action
from app.services.finance_service import finance_totals

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
MAX_BULK_STUDENTS = 2000
STATES = ("unpaid", "overdue", "partially_paid", "pending", "paid", "cancelled")


def _paid_subquery(tenant_id: uuid.UUID):
    return (
        select(Payment.invoice_id.label("invoice_id"), func.sum(Payment.amount).label("paid"))
        .where(Payment.tenant_id == tenant_id)
        .group_by(Payment.invoice_id)
        .subquery()
    )


def _state(amount_due: float, paid: float, due: date, cancelled: bool, today: date) -> tuple[str, int]:
    if cancelled:
        return "cancelled", 0
    balance = round(amount_due - paid, 2)
    if balance <= 0:
        return "paid", 0
    if due < today:
        return "overdue", (today - due).days
    return ("partially_paid" if paid > 0 else "pending"), 0


def list_invoice_rows(
    db: Session, *, tenant_id: uuid.UUID, q: str | None = None, class_id: uuid.UUID | None = None,
    academic_year: str | None = None, state: str | None = None, sort: str = "due",
    limit: int = DEFAULT_PAGE_SIZE, offset: int = 0, today: date | None = None,
) -> tuple[list[dict], int]:
    if state is not None and state not in STATES:
        raise HTTPException(status_code=422, detail=f"État inconnu : {state}.")
    today = today or date.today()
    limit, offset = max(1, min(limit, MAX_PAGE_SIZE)), max(0, offset)
    paid_sq = _paid_subquery(tenant_id)
    paid = func.coalesce(paid_sq.c.paid, 0)
    balance = Invoice.amount_due - paid
    cancelled = Invoice.status == InvoiceStatus.CANCELLED

    conditions = [Invoice.tenant_id == tenant_id]
    if academic_year:
        conditions.append(Invoice.academic_year == academic_year)
    if class_id is not None:
        conditions.append(Student.class_id == class_id)
    if state == "cancelled":
        conditions.append(cancelled)
    elif state is not None:
        conditions.append(~cancelled)
        if state == "paid":
            conditions.append(balance <= 0)
        else:
            conditions.append(balance > 0)
            if state == "overdue":
                conditions.append(Invoice.due_date < today)
            elif state == "partially_paid":
                conditions.append(Invoice.due_date >= today)
                conditions.append(paid > 0)
            elif state == "pending":
                conditions.append(Invoice.due_date >= today)
                conditions.append(paid == 0)
    else:
        conditions.append(~cancelled)  # par défaut : tout sauf les annulées
    for token in (q or "").strip()[:100].split()[:5]:
        pattern = "%" + token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(or_(
            Student.first_name.ilike(pattern, escape="\\"), Student.last_name.ilike(pattern, escape="\\"),
            Student.matricule.ilike(pattern, escape="\\"), Invoice.label.ilike(pattern, escape="\\"),
        ))

    base = (
        select(Invoice, Student, SchoolClass.name, paid.label("paid"))
        .join(Student, Student.id == Invoice.student_id)
        .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
        .outerjoin(paid_sq, paid_sq.c.invoice_id == Invoice.id)
        .where(*conditions)
    )
    total = db.execute(
        select(func.count()).select_from(Invoice)
        .join(Student, Student.id == Invoice.student_id)
        .outerjoin(paid_sq, paid_sq.c.invoice_id == Invoice.id)
        .where(*conditions)
    ).scalar_one()
    order = (
        [balance.desc(), Invoice.due_date, Invoice.id] if sort == "balance"
        else [Invoice.due_date, func.lower(Student.last_name), Invoice.id]
    )
    rows = db.execute(base.order_by(*order).limit(limit).offset(offset)).all()
    out = []
    for inv, stu, class_name, paid_value in rows:
        st, late = _state(float(inv.amount_due), float(paid_value), inv.due_date, inv.status == InvoiceStatus.CANCELLED, today)
        out.append({
            "id": inv.id, "student_id": stu.id, "student_name": f"{stu.last_name} {stu.first_name}",
            "class_name": class_name, "label": inv.label, "academic_year": inv.academic_year,
            "amount_due": float(inv.amount_due), "amount_paid": float(paid_value),
            "balance": round(float(inv.amount_due) - float(paid_value), 2), "due_date": inv.due_date,
            "state": st, "days_overdue": late,
        })
    return out, int(total)


def finance_summary(db: Session, *, tenant_id: uuid.UUID, academic_year: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    current = current_year(db, tenant_id)
    year = academic_year or current
    paid_sq = _paid_subquery(tenant_id)
    paid = func.coalesce(paid_sq.c.paid, 0)
    balance = Invoice.amount_due - paid
    live = Invoice.status != InvoiceStatus.CANCELLED
    unpaid = balance > 0
    overdue = unpaid & (Invoice.due_date < today)

    def bucket(lo: int, hi: int | None):
        # Retard de lo à hi jours (inclus) = échéance entre today-hi et today-lo ; comparaisons de dates, pas d'arithmétique SQL.
        cond = overdue & (Invoice.due_date <= today - timedelta(days=lo))
        if hi is not None:
            cond = cond & (Invoice.due_date >= today - timedelta(days=hi))
        return func.coalesce(func.sum(case((cond, balance), else_=0)), 0)

    base_where = (Invoice.tenant_id == tenant_id, Invoice.academic_year == year, live)
    row = db.execute(
        select(
            func.coalesce(func.sum(Invoice.amount_due), 0), func.coalesce(func.sum(paid), 0),
            func.coalesce(func.sum(case((overdue, balance), else_=0)), 0),
            func.count(case((overdue, 1))), func.count(case((unpaid, 1))),
            bucket(1, 30), bucket(31, 60), bucket(61, 90), bucket(91, None),
        ).select_from(Invoice).outerjoin(paid_sq, paid_sq.c.invoice_id == Invoice.id).where(*base_where)
    ).one()
    due_total, paid_total, overdue_amount, overdue_n, unpaid_n, b30, b60, b90, b90p = row

    class_rows = db.execute(
        select(
            Student.class_id, SchoolClass.name, func.sum(Invoice.amount_due), func.sum(paid),
            func.count(func.distinct(case((unpaid, Invoice.student_id)))),
        ).select_from(Invoice)
        .join(Student, Student.id == Invoice.student_id)
        .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
        .outerjoin(paid_sq, paid_sq.c.invoice_id == Invoice.id)
        .where(*base_where).group_by(Student.class_id, SchoolClass.name)
        .order_by(func.coalesce(func.sum(Invoice.amount_due), 0).desc())
    ).all()

    # Arriérés (années antérieures à l'année en cours de l'établissement) : même définition que les Rapports.
    arrears = finance_totals(db, tenant_id=tenant_id, year=current)["previous_years_outstanding"]
    due_f, paid_f = float(due_total), float(paid_total)
    return {
        "academic_year": year, "due": due_f, "paid": paid_f, "outstanding": round(due_f - paid_f, 2),
        "recovery_rate_percent": round(100 * paid_f / due_f, 1) if due_f else None,
        "overdue_amount": round(float(overdue_amount), 2), "overdue_invoices": int(overdue_n), "unpaid_invoices": int(unpaid_n),
        "aging": {"1-30 j": float(b30), "31-60 j": float(b60), "61-90 j": float(b90), "plus de 90 j": float(b90p)},
        "previous_years_outstanding": arrears,
        "by_class": [
            {"class_id": cid, "class_name": name or "Sans classe", "due": float(d), "paid": float(p),
             "outstanding": round(float(d) - float(p), 2), "students_with_balance": int(n)}
            for cid, name, d, p, n in class_rows
        ],
    }


def bulk_invoice_class(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, data: BulkInvoiceRequest, commit: bool,
) -> BulkInvoiceReport:
    """Facture d'un coup tous les élèves actifs d'une classe (scolarité, frais d'examen…).

    Rejouable sans doublon : un élève déjà facturé avec le MÊME libellé pour la
    MÊME année est ignoré (et comptabilisé « déjà facturé »). Un seul lancement
    à la fois par établissement (verrou), pour qu'un double clic ne facture pas deux fois."""
    school_class = _get_class_or_404(db, tenant_id=tenant_id, class_id=data.class_id)
    if commit:
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"bulk-invoice:{tenant_id}"})
    current = ensure_academic_year(db, tenant_id) if commit else current_year(db, tenant_id)
    year = data.academic_year or current
    if not is_valid_year(year) or year > next_year(current):
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Année scolaire invalide pour une facture (au plus {next_year(current)}).")

    students = list(db.execute(
        select(Student.id).where(
            Student.tenant_id == tenant_id, Student.class_id == data.class_id, Student.status == StudentStatus.ACTIVE
        ).order_by(Student.id)
    ).scalars())
    if not students:
        db.rollback()
        raise HTTPException(status_code=409, detail="Aucun élève actif dans cette classe.")
    if len(students) > MAX_BULK_STUDENTS:
        db.rollback()
        raise HTTPException(status_code=413, detail=f"Classe trop grande pour une facturation en une fois (maximum {MAX_BULK_STUDENTS}).")

    already = set(db.execute(
        select(Invoice.student_id).where(
            Invoice.tenant_id == tenant_id, Invoice.student_id.in_(students), Invoice.academic_year == year,
            func.lower(Invoice.label) == data.label.lower(), Invoice.status != InvoiceStatus.CANCELLED,
        )
    ).scalars())
    todo = [s for s in students if s not in already]
    if commit and todo:
        db.add_all([
            Invoice(tenant_id=tenant_id, student_id=s, label=data.label, academic_year=year,
                    amount_due=data.amount_due, due_date=data.due_date)
            for s in todo
        ])
        log_action(
            db, tenant_id=tenant_id, actor_user_id=actor_id, action="invoices.bulk_created", target_type="SchoolClass",
            target_id=str(data.class_id),
            metadata={"label": data.label, "academic_year": year, "amount_due": data.amount_due,
                      "created": len(todo), "already_billed": len(already)},
        )
    if commit:
        db.commit()
    return BulkInvoiceReport(
        dry_run=not commit, class_name=school_class.name, academic_year=year, students=len(students),
        created=len(todo), already_billed=len(already), total_amount=round(len(todo) * data.amount_due, 2),
    )
