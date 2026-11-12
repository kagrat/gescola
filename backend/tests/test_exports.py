"""AU-11 : exports Excel (élèves, finances, présences)."""
import io
from datetime import date, timedelta

from openpyxl import load_workbook
from sqlalchemy import select

from app.db.session import SessionLocal, set_tenant_context
from app.models.audit import AuditLog
from app.models.user import UserRole
from app.services.export_service import safe_cell

API = "/api/v1"
TODAY = date.today()


class S:
    pass


def _school(client, make_tenant, make_user, auth_headers):
    s = S()
    s.tenant = make_tenant()
    mk = lambda role: (lambda u, p: (u, auth_headers(u, p)))(*make_user(tenant=s.tenant, role=role))
    s.admin, s.h = mk(UserRole.SCHOOL_ADMIN)
    s.acc, s.acc_h = mk(UserRole.ACCOUNTANT)
    s.staff, s.staff_h = mk(UserRole.STAFF)
    s.teacher, s.teacher_h = mk(UserRole.TEACHER)
    s.parent, s.parent_h = mk(UserRole.PARENT)
    mkc = lambda n, lv: client.post(f"{API}/classes", json={"name": n, "level": lv}, headers=s.h).json()
    s.c6, s.c5 = mkc("6ème A", "6ème"), mkc("5ème A", "5ème")
    mks = lambda f, l, c: client.post(f"{API}/students", json={"first_name": f, "last_name": l, "class_id": c["id"] if c else None,
                                                              "matricule": f"M-{l[:3]}", "guardian_phone": "+22900000000"}, headers=s.h).json()
    s.ada, s.bao, s.cleo, s.dan = mks("Ada", "ZOHOUN", s.c6), mks("Bao", "AGBO", s.c6), mks("Cléo", "DOSSOU", s.c5), mks("Dan", "FADO", None)
    return s


def _xlsx(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "attachment" in resp.headers["content-disposition"] and ".xlsx" in resp.headers["content-disposition"]
    assert resp.headers["cache-control"] == "private, no-store"
    return load_workbook(io.BytesIO(resp.content))


def _rows(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


# ---------- anti-injection ----------

def test_safe_cell_neutralises_formulas_and_keeps_data_intact():
    for evil in ("=1+1", "+1+1", "-2+3", "+HACK", "-cmd", "@SUM(A1)", "\t=cmd", "\r=x", '=HYPERLINK("http://x","y")'):
        assert safe_cell(evil).startswith("'"), evil
    assert safe_cell("+229 97 00 00 00") == "+229 97 00 00 00" and safe_cell("+22900000000") == "+22900000000" and safe_cell("(+229) 97-00") == "(+229) 97-00"
    assert safe_cell("Jean-Paul") == "Jean-Paul" and safe_cell("Agbo") == "Agbo" and safe_cell("12 rue-A") == "12 rue-A"
    assert safe_cell(12) == 12 and safe_cell(None) is None and safe_cell(date(2026, 1, 2)) == date(2026, 1, 2) and safe_cell(-5.5) == -5.5
    assert safe_cell("a\x00b\x07c") == "abc"


# ---------- élèves ----------

def test_students_export_content_filters_and_headers(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post(f"{API}/students/{s.bao['id']}/status", json={"status": "transferred", "reason": "Départ"}, headers=s.h)
    client.put(f"{API}/students/{s.ada['id']}/fee-discount", json={"percent": 25}, headers=s.h)
    ws = _xlsx(client.get(f"{API}/exports/students", headers=s.staff_h))["Élèves"]
    rows = _rows(ws)
    assert rows[0][:7] == ["Matricule", "Nom", "Prénom", "Sexe", "Date de naissance", "Classe", "Statut"]
    # tri : classe (5ème A avant 6ème A, sans classe à la fin), puis nom
    assert [r[1] for r in rows[1:]] == ["DOSSOU", "AGBO", "ZOHOUN", "FADO"]
    by = {r[1]: r for r in rows[1:]}
    assert by["AGBO"][6] == "Transféré" and by["ZOHOUN"][11] == 25.0 and not by["FADO"][5] and by["ZOHOUN"][9] == "+22900000000"
    only6 = _rows(_xlsx(client.get(f"{API}/exports/students", params={"class_id": s.c6["id"]}, headers=s.h))["Élèves"])
    assert sorted(r[1] for r in only6[1:]) == ["AGBO", "ZOHOUN"]
    active = _rows(_xlsx(client.get(f"{API}/exports/students", params={"status": "active"}, headers=s.h))["Élèves"])
    assert "AGBO" not in [r[1] for r in active[1:]] and len(active) == 4


def test_a_malicious_student_name_cannot_become_a_formula(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post(f"{API}/students", json={"first_name": "=cmd|' /C calc'!A0", "last_name": "+HACK", "guardian_name": "@SUM(1+1)"}, headers=s.h)
    ws = _xlsx(client.get(f"{API}/exports/students", headers=s.h))["Élèves"]
    evil = next(r for r in _rows(ws)[1:] if "HACK" in (r[1] or ""))
    assert evil[1] == "'+HACK" and evil[2].startswith("'=") and evil[8] == "'@SUM(1+1)"
    for row in ws.iter_rows(min_row=2):
        for c in row:
            assert c.data_type != "f", c.coordinate                                   # aucune cellule n'est une formule
    assert next(r for r in ws.iter_rows(min_row=2) if "HACK" in str(r[1].value))[1].data_type == "s"


def test_students_export_access_isolation_and_audit(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    for h in (s.teacher_h, s.acc_h, s.parent_h):
        assert client.get(f"{API}/exports/students", headers=h).status_code == 403
    assert client.get(f"{API}/exports/students").status_code in (401, 403)
    assert client.get(f"{API}/exports/students", params={"class_id": other.c6["id"]}, headers=s.h).status_code == 404
    assert len(_rows(_xlsx(client.get(f"{API}/exports/students", headers=other.h))["Élèves"])) == 5            # chacun ses élèves
    client.get(f"{API}/exports/students", headers=s.h)
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        log = db.execute(select(AuditLog).where(AuditLog.action == "export.generated")).scalars().all()
        assert log[-1].actor_user_id == s.admin.id and log[-1].metadata_json["rows"] == 4 and log[-1].metadata_json["kind"] == "students"
    finally:
        db.close()


def test_export_refuses_oversized_results(client, make_tenant, make_user, auth_headers, monkeypatch):
    from app.services import export_service

    s = _school(client, make_tenant, make_user, auth_headers)
    monkeypatch.setattr(export_service, "MAX_ROWS", 2)
    assert client.get(f"{API}/exports/students", headers=s.h).status_code == 413


# ---------- finances ----------

def _finance_world(client, s):
    inv = lambda stu, amt, days, label: client.post(f"{API}/invoices", json={"student_id": stu["id"], "label": label, "amount_due": amt,
                                                   "due_date": str(TODAY + timedelta(days=days))}, headers=s.h).json()
    i1 = inv(s.ada, 30000, -45, "Scolarité")
    i2 = inv(s.bao, 20000, 20, "=EVIL()")
    client.post(f"{API}/payments", json={"invoice_id": i1["id"], "amount": 10000, "method": "mobile_money", "reference": "+MM-1"}, headers=s.acc_h)
    return i1, i2


def test_finance_export_matches_the_screens(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _finance_world(client, s)
    wb = _xlsx(client.get(f"{API}/exports/finance", headers=s.acc_h))
    assert wb.sheetnames == ["Synthèse", "Factures", "Encaissements"]
    summary = client.get(f"{API}/finance/summary", headers=s.h).json()
    syn = {r[0]: r[1] for r in _rows(wb["Synthèse"])[1:]}
    assert syn["Facturé (F)"] == summary["due"] == 50000.0 and syn["Encaissé (F)"] == summary["paid"] == 10000.0
    assert syn["Reste à recouvrer (F)"] == 40000.0 and syn["En retard (F)"] == summary["overdue_amount"] == 20000.0
    assert syn["Retard 31-60 j (F)"] == 20000.0 and syn["Classe 6ème A — reste dû (F)"] == 40000.0
    inv = _rows(wb["Factures"])
    assert inv[0][:3] == ["Élève", "Classe", "Libellé"] and len(inv) == 3
    ada = next(r for r in inv[1:] if r[0] == "ZOHOUN Ada")
    assert ada[4:7] == [30000.0, 10000.0, 20000.0] and ada[8] == "En retard" and ada[9] == 45 and isinstance(ada[7], __import__("datetime").datetime)
    pay = _rows(wb["Encaissements"])
    assert pay[1][0] == 1 and pay[1][2] == "ZOHOUN Ada" and pay[1][5] == 10000.0 and pay[1][6] == "Mobile Money"


def test_finance_export_filters_and_formula_safety(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _finance_world(client, s)
    wb = _xlsx(client.get(f"{API}/exports/finance", params={"state": "overdue"}, headers=s.h))
    assert [r[0] for r in _rows(wb["Factures"])[1:]] == ["ZOHOUN Ada"]
    wb = _xlsx(client.get(f"{API}/exports/finance", headers=s.h))
    labels = [r[2] for r in _rows(wb["Factures"])[1:]]
    assert "'=EVIL()" in labels and _rows(wb["Encaissements"])[1][7] == "'+MM-1"
    for ws in wb:
        for row in ws.iter_rows():
            assert all(c.data_type != "f" for c in row)
    assert client.get(f"{API}/exports/finance", params={"state": "bogus"}, headers=s.h).status_code == 422
    assert client.get(f"{API}/exports/finance", params={"academic_year": "26-27"}, headers=s.h).status_code == 422


def test_finance_export_access_and_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    _finance_world(client, s)
    for h in (s.staff_h, s.teacher_h, s.parent_h):
        assert client.get(f"{API}/exports/finance", headers=h).status_code == 403
    wb = _xlsx(client.get(f"{API}/exports/finance", headers=other.h))
    assert len(_rows(wb["Factures"])) == 1 and len(_rows(wb["Encaissements"])) == 1               # en-têtes seulement
    assert client.get(f"{API}/exports/finance", params={"class_id": other.c6["id"]}, headers=s.h).status_code == 404


# ---------- présences ----------

def test_attendance_export_summary_and_detail(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    day = lambda n: str(TODAY - timedelta(days=n))
    for stu, d, st, j in ((s.ada, 1, "absent", False), (s.ada, 2, "absent", True), (s.ada, 3, "late", False), (s.bao, 1, "absent", False),
                          (s.cleo, 1, "absent", False), (s.ada, 400, "absent", False)):
        r = client.post(f"{API}/attendance", json={"student_id": stu["id"], "date": day(d), "status": st, "justified": j}, headers=s.h)
        assert r.status_code == 201, r.text
    params = {"date_from": day(10), "date_to": day(0)}
    wb = _xlsx(client.get(f"{API}/exports/attendance", params=params, headers=s.staff_h))
    rec = _rows(wb["Récapitulatif"])
    assert rec[0] == ["Élève", "Classe", "Absences", "dont non justifiées", "Retards"]
    ada = next(r for r in rec[1:] if r[0] == "ZOHOUN Ada")
    assert ada[2:] == [2, 1, 1]                                                                   # l'absence d'il y a 400 jours est hors période
    assert len(_rows(wb["Détail"])) == 1 + 5
    only6 = _xlsx(client.get(f"{API}/exports/attendance", params={**params, "class_id": s.c6["id"]}, headers=s.h))
    assert sorted(r[0] for r in _rows(only6["Récapitulatif"])[1:]) == ["AGBO Bao", "ZOHOUN Ada"]


def test_attendance_export_validation_access_and_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    ok = {"date_from": str(TODAY - timedelta(days=5)), "date_to": str(TODAY)}
    assert client.get(f"{API}/exports/attendance", params={"date_from": str(TODAY), "date_to": str(TODAY - timedelta(days=1))}, headers=s.h).status_code == 422
    assert client.get(f"{API}/exports/attendance", params={"date_from": str(TODAY - timedelta(days=366)), "date_to": str(TODAY)}, headers=s.h).status_code == 422
    assert client.get(f"{API}/exports/attendance", params={"date_from": str(TODAY - timedelta(days=365)), "date_to": str(TODAY)}, headers=s.h).status_code == 200
    assert client.get(f"{API}/exports/attendance", params={"date_from": "n'importe quoi", "date_to": str(TODAY)}, headers=s.h).status_code == 422
    assert client.get(f"{API}/exports/attendance", headers=s.h).status_code == 422
    for h in (s.teacher_h, s.acc_h, s.parent_h):
        assert client.get(f"{API}/exports/attendance", params=ok, headers=h).status_code == 403
    assert client.get(f"{API}/exports/attendance", params={**ok, "class_id": other.c6["id"]}, headers=s.h).status_code == 404
