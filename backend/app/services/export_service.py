"""Exports Excel (.xlsx) : élèves, finances, présences (AU-11).

Règles :
  * AUCUNE injection de formule : toute cellule texte est écrite comme TEXTE
    (jamais comme formule) et, si elle commence par = + - @ (hors numéros de
    téléphone), préfixée d'une apostrophe, car les noms, libellés et références
    saisis par des utilisateurs s'ouvriraient sinon comme des formules (vol de
    données, exécution via DDE) dans Excel ou en cas de réexport en CSV ;
  * mêmes filtres et mêmes calculs que les écrans (les montants viennent des
    services de finance, pas d'un second calcul) ;
  * plafonné (20 000 lignes) pour ne pas saturer le serveur ; au-delà, 413 ;
  * chaque export est tracé au journal d'audit (qui, quoi, combien de lignes) :
    une liste d'élèves est une donnée sensible.
"""
import io
import re
import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass
from app.models.attendance import Attendance, AttendanceStatus
from app.models.finance import Invoice, Payment
from app.models.student import Student, StudentStatus
from app.services.academic_service import _get_class_or_404
from app.services.academic_year_service import current_year
from app.services.audit_service import log_action
from app.services.finance_overview_service import MAX_PAGE_SIZE, finance_summary, list_invoice_rows

MAX_ROWS = 20_000
MAX_ATTENDANCE_DAYS = 366
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

STATUS_FR = {"active": "Actif", "transferred": "Transféré", "graduated": "Diplômé", "archived": "Archivé"}
GENDER_FR = {"male": "Masculin", "female": "Féminin"}
STATE_FR = {"paid": "Soldée", "pending": "À échoir", "partially_paid": "Partielle", "overdue": "En retard", "cancelled": "Annulée"}
METHOD_FR = {"cash": "Espèces", "mobile_money": "Mobile Money", "bank_transfer": "Virement"}
ATT_FR = {"present": "Présent", "absent": "Absent", "late": "En retard"}

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r", "\n")
# Un numéro de téléphone (« +229 97 00 00 00 », « -5 ») commence par + ou - sans être une formule : on le garde tel quel.
_PHONE_OR_NUMBER = re.compile(r"^[+-]?[\d\s().,-]+$")


def safe_cell(value):
    """Neutralise l'injection de formule (OWASP « CSV injection ») ; laisse nombres, dates et booléens intacts."""
    if isinstance(value, str):
        value = "".join(ch for ch in value if ch >= " " or ch in "\t\n")  # retire les caractères de contrôle
        if value.startswith(_DANGEROUS) and not (value[0] in "+-" and _PHONE_OR_NUMBER.match(value)):
            return "'" + value
    return value


def _sheet(wb: Workbook, title: str, headers: list[str], rows: list[list], *, first: bool = False, money: tuple[int, ...] = ()):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title[:31]
    ws.append([safe_cell(h) for h in headers])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="123B73")
        c.alignment = Alignment(vertical="center")
    for r in rows:
        ws.append([safe_cell(v) for v in r])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, str):
                c.data_type = "s"  # texte pur : jamais interprété comme une formule, même s'il commence par « = »
    for idx in money:
        for (cell,) in ws.iter_rows(min_row=2, min_col=idx, max_col=idx):
            cell.number_format = '#,##0'
    for i, h in enumerate(headers, start=1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:300] if i - 1 < len(r) and r[i - 1] is not None])
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 48)
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = ws.dimensions
    return ws


def _bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _audit(db: Session, *, tenant_id, actor_id, kind: str, rows: int, filters: dict) -> None:
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="export.generated", target_type="Export", target_id=kind,
               metadata={"kind": kind, "rows": rows, "filters": {k: str(v) for k, v in filters.items() if v is not None}})
    db.commit()


# ---------------- Élèves ----------------

def export_students(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, class_id: uuid.UUID | None, student_status: StudentStatus | None) -> bytes:
    if class_id is not None:
        _get_class_or_404(db, tenant_id=tenant_id, class_id=class_id)
    q = (select(Student, SchoolClass.name).outerjoin(SchoolClass, Student.class_id == SchoolClass.id).where(Student.tenant_id == tenant_id))
    if class_id is not None:
        q = q.where(Student.class_id == class_id)
    if student_status is not None:
        q = q.where(Student.status == student_status)
    rows = db.execute(q.order_by(SchoolClass.name.nulls_last(), Student.last_name, Student.first_name, Student.id).limit(MAX_ROWS + 1)).all()
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"Trop de lignes (maximum {MAX_ROWS:,}). Filtrez par classe.".replace(",", " "))
    wb = Workbook()
    _sheet(wb, "Élèves", ["Matricule", "Nom", "Prénom", "Sexe", "Date de naissance", "Classe", "Statut", "Redoublant", "Tuteur", "Téléphone", "E-mail", "Remise frais (%)"], [
        [s.matricule, s.last_name, s.first_name, GENDER_FR.get(s.gender.value if s.gender else "", ""), s.date_of_birth, cname or "",
         STATUS_FR.get(s.status.value, s.status.value), "Oui" if s.is_repeater else "Non", s.guardian_name, s.guardian_phone, s.guardian_email,
         float(s.fee_discount_percent)] for s, cname in rows], first=True)
    ws = wb["Élèves"]
    for (cell,) in ws.iter_rows(min_row=2, min_col=5, max_col=5):
        cell.number_format = "DD/MM/YYYY"
    _audit(db, tenant_id=tenant_id, actor_id=actor_id, kind="students", rows=len(rows), filters={"class_id": class_id, "status": student_status.value if student_status else None})
    return _bytes(wb)


# ---------------- Finances ----------------

def export_finance(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, academic_year: str | None, class_id: uuid.UUID | None, state: str | None) -> bytes:
    if class_id is not None:
        _get_class_or_404(db, tenant_id=tenant_id, class_id=class_id)
    invoices, offset = [], 0
    while True:
        page, total = list_invoice_rows(db, tenant_id=tenant_id, class_id=class_id, academic_year=academic_year, state=state, limit=MAX_PAGE_SIZE, offset=offset)
        invoices += page
        offset += MAX_PAGE_SIZE
        if total > MAX_ROWS:
            raise HTTPException(status_code=413, detail=f"Trop de lignes (maximum {MAX_ROWS:,}). Filtrez par classe ou par état.".replace(",", " "))
        if offset >= total or not page:
            break
    year = academic_year or current_year(db, tenant_id)
    summary = finance_summary(db, tenant_id=tenant_id, academic_year=year)

    pay_q = (select(Payment, Invoice, Student, SchoolClass.name)
             .join(Invoice, Payment.invoice_id == Invoice.id).join(Student, Invoice.student_id == Student.id)
             .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
             .where(Payment.tenant_id == tenant_id, Invoice.academic_year == year))
    if class_id is not None:
        pay_q = pay_q.where(Student.class_id == class_id)
    pays = db.execute(pay_q.order_by(Payment.receipt_number).limit(MAX_ROWS + 1)).all()
    if len(pays) > MAX_ROWS:
        raise HTTPException(status_code=413, detail="Trop d'encaissements : filtrez par classe.")

    wb = Workbook()
    rate = summary["recovery_rate_percent"]
    _sheet(wb, "Synthèse", ["Indicateur", "Valeur"], [
        ["Année scolaire", summary["academic_year"]], ["Facturé (F)", summary["due"]], ["Encaissé (F)", summary["paid"]],
        ["Reste à recouvrer (F)", summary["outstanding"]], ["Taux de recouvrement (%)", rate if rate is not None else ""],
        ["En retard (F)", summary["overdue_amount"]], ["Factures en retard", summary["overdue_invoices"]],
        *[[f"Retard {k} (F)", v] for k, v in summary["aging"].items()],
        ["Arriérés d'années précédentes (F)", summary["previous_years_outstanding"]],
        *[[f"Classe {c['class_name']} — reste dû (F)", c["outstanding"]] for c in summary["by_class"]],
    ], first=True, money=(2,))
    _sheet(wb, "Factures", ["Élève", "Classe", "Libellé", "Année", "Dû (F)", "Payé (F)", "Reste (F)", "Échéance", "État", "Jours de retard"], [
        [r["student_name"], r["class_name"] or "", r["label"], r["academic_year"], r["amount_due"], r["amount_paid"], r["balance"],
         r["due_date"], STATE_FR.get(r["state"], r["state"]), r["days_overdue"]] for r in invoices], money=(5, 6, 7))
    _sheet(wb, "Encaissements", ["N° reçu", "Date", "Élève", "Classe", "Facture", "Montant (F)", "Mode", "Référence"], [
        [p.receipt_number, p.created_at.date(), f"{s.last_name.upper()} {s.first_name}", cname or "", i.label, float(p.amount),
         METHOD_FR.get(p.method.value, p.method.value), p.reference] for p, i, s, cname in pays], money=(6,))
    for (cell,) in wb["Factures"].iter_rows(min_row=2, min_col=8, max_col=8):
        cell.number_format = "DD/MM/YYYY"
    for (cell,) in wb["Encaissements"].iter_rows(min_row=2, min_col=2, max_col=2):
        cell.number_format = "DD/MM/YYYY"
    _audit(db, tenant_id=tenant_id, actor_id=actor_id, kind="finance", rows=len(invoices) + len(pays),
           filters={"academic_year": year, "class_id": class_id, "state": state})
    return _bytes(wb)


# ---------------- Présences ----------------

def export_attendance(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, class_id: uuid.UUID | None, date_from: date, date_to: date) -> bytes:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="La date de fin précède la date de début.")
    if (date_to - date_from).days + 1 > MAX_ATTENDANCE_DAYS:
        raise HTTPException(status_code=422, detail=f"Période trop longue (maximum {MAX_ATTENDANCE_DAYS} jours).")
    if class_id is not None:
        _get_class_or_404(db, tenant_id=tenant_id, class_id=class_id)
    q = (select(Attendance, Student, SchoolClass.name).join(Student, Attendance.student_id == Student.id)
         .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
         .where(Attendance.tenant_id == tenant_id, Attendance.date >= date_from, Attendance.date <= date_to))
    if class_id is not None:
        q = q.where(Student.class_id == class_id)
    rows = db.execute(q.order_by(Attendance.date, SchoolClass.name.nulls_last(), Student.last_name, Student.first_name).limit(MAX_ROWS + 1)).all()
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail="Trop de lignes : réduisez la période ou filtrez par classe.")

    per: dict[uuid.UUID, dict] = {}
    for a, s, cname in rows:
        d = per.setdefault(s.id, {"name": f"{s.last_name.upper()} {s.first_name}", "class": cname or "", "absent": 0, "unjustified": 0, "late": 0})
        if a.status == AttendanceStatus.ABSENT:
            d["absent"] += 1
            d["unjustified"] += 0 if a.justified else 1
        elif a.status == AttendanceStatus.LATE:
            d["late"] += 1
    wb = Workbook()
    _sheet(wb, "Récapitulatif", ["Élève", "Classe", "Absences", "dont non justifiées", "Retards"],
           [[d["name"], d["class"], d["absent"], d["unjustified"], d["late"]] for d in sorted(per.values(), key=lambda x: (-x["unjustified"], x["name"]))], first=True)
    _sheet(wb, "Détail", ["Date", "Élève", "Classe", "Statut", "Justifiée"],
           [[a.date, f"{s.last_name.upper()} {s.first_name}", cname or "", ATT_FR.get(a.status.value, a.status.value),
             "Oui" if a.justified else "Non"] for a, s, cname in rows])
    for (cell,) in wb["Détail"].iter_rows(min_row=2, min_col=1, max_col=1):
        cell.number_format = "DD/MM/YYYY"
    _audit(db, tenant_id=tenant_id, actor_id=actor_id, kind="attendance", rows=len(rows),
           filters={"class_id": class_id, "from": date_from, "to": date_to})
    return _bytes(wb)
