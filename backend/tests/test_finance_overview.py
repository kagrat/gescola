"""AU-09 : vue financière globale, facturation d'une classe, solidité des encaissements."""
import threading
from datetime import date, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal, set_tenant_context
from app.models.audit import AuditLog
from app.models.user import UserRole
from app.services.academic_year_service import default_academic_year, next_year

API = "/api/v1"
TODAY = date.today()
YEAR = default_academic_year(TODAY)
PREV = f"{int(YEAR[:4]) - 1}-{YEAR[:4]}"


class School:
    pass


def _school(client, make_tenant, make_user, auth_headers):
    s = School()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    s.h = auth_headers(s.admin, pwd)
    s.acc, ap = make_user(tenant=s.tenant, role=UserRole.ACCOUNTANT)
    s.acc_h = auth_headers(s.acc, ap)
    mk = lambda n, lv: client.post(f"{API}/classes", json={"name": n, "level": lv}, headers=s.h).json()
    s.c6, s.c5 = mk("6ème A", "6ème"), mk("5ème A", "5ème")

    def stu(first, last, cls):
        return client.post(f"{API}/students", json={"first_name": first, "last_name": last, "class_id": cls["id"] if cls else None}, headers=s.h).json()

    s.ada, s.bao, s.cleo, s.dan = stu("Ada", "ZOHOUN", s.c6), stu("Bao", "AGBO", s.c6), stu("Cléo", "DOSSOU", s.c5), stu("Dan", "FADO", None)
    return s


def _inv(client, s, student, amount, due, label="Scolarité", year=None):
    body = {"student_id": student["id"], "label": label, "amount_due": amount, "due_date": str(due)}
    if year:
        body["academic_year"] = year
    r = client.post(f"{API}/invoices", json=body, headers=s.h)
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, s, invoice, amount, expect=201, headers=None):
    r = client.post(f"{API}/payments", json={"invoice_id": invoice["id"], "amount": amount, "method": "cash"}, headers=headers or s.h)
    assert r.status_code == expect, r.text
    return r


def _rows(client, s, **params):
    r = client.get(f"{API}/finance/invoices", params=params, headers=s.h)
    assert r.status_code == 200, r.text
    return r.json(), int(r.headers["X-Total-Count"])


def _populate(client, s):
    """Ada: 30 000 payée 10 000, échue depuis 45 j · Bao: 30 000 non payée, à échoir · Cléo: 50 000 soldée · Dan (sans classe): 20 000 échue depuis 100 j."""
    s.i_ada = _inv(client, s, s.ada, 30000, TODAY - timedelta(days=45))
    _pay(client, s, s.i_ada, 10000)
    s.i_bao = _inv(client, s, s.bao, 30000, TODAY + timedelta(days=20))
    s.i_cleo = _inv(client, s, s.cleo, 50000, TODAY - timedelta(days=10))
    _pay(client, s, s.i_cleo, 50000)
    s.i_dan = _inv(client, s, s.dan, 20000, TODAY - timedelta(days=100))


# ======================= Liste =======================

def test_states_are_computed_at_read_time_not_trusted_from_the_stored_field(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _populate(client, s)
    rows, total = _rows(client, s)
    assert total == 4
    by = {r["student_name"]: r for r in rows}
    assert by["ZOHOUN Ada"]["state"] == "overdue" and by["ZOHOUN Ada"]["days_overdue"] == 45 and by["ZOHOUN Ada"]["balance"] == 20000.0
    assert by["AGBO Bao"]["state"] == "pending" and by["AGBO Bao"]["days_overdue"] == 0
    assert by["DOSSOU Cléo"]["state"] == "paid" and by["DOSSOU Cléo"]["balance"] == 0
    assert by["FADO Dan"]["class_name"] is None and by["FADO Dan"]["days_overdue"] == 100
    # tri par défaut : échéance la plus ancienne d'abord (les plus en retard en tête)
    assert [r["student_name"] for r in rows] == ["FADO Dan", "ZOHOUN Ada", "DOSSOU Cléo", "AGBO Bao"]
    # tri par solde : le plus gros reste dû d'abord (30 000, 20 000, 20 000, 0)
    assert [r["balance"] for r in _rows(client, s, sort="balance")[0]] == [30000.0, 20000.0, 20000.0, 0.0]


def test_filters_by_state_class_year_and_search(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _populate(client, s)
    names = lambda **p: sorted(r["student_name"] for r in _rows(client, s, **p)[0])
    assert names(state="overdue") == ["FADO Dan", "ZOHOUN Ada"]
    assert names(state="unpaid") == ["AGBO Bao", "FADO Dan", "ZOHOUN Ada"]
    assert names(state="paid") == ["DOSSOU Cléo"]
    assert names(state="pending") == ["AGBO Bao"]
    assert names(state="partially_paid") == []                     # Ada est partielle MAIS échue : elle est « overdue »
    assert names(class_id=s.c6["id"]) == ["AGBO Bao", "ZOHOUN Ada"]
    assert names(q="dossou") == ["DOSSOU Cléo"]
    assert names(q="zohoun ada") == ["ZOHOUN Ada"]
    assert names(q="%") == []                                      # les jokers saisis sont littéraux
    old = _inv(client, s, s.ada, 5000, TODAY - timedelta(days=400), label="Ancien", year=PREV)
    assert names(academic_year=PREV) == ["ZOHOUN Ada"] and len(names(academic_year=YEAR)) == 4
    assert client.get(f"{API}/finance/invoices", params={"state": "bogus"}, headers=s.h).status_code == 422
    assert old["academic_year"] == PREV


def test_pagination_is_bounded_and_totals_are_exact(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    for i in range(7):
        _inv(client, s, s.ada, 1000 + i, TODAY + timedelta(days=i), label=f"Frais {i}")
    page1, total = _rows(client, s, limit=3, offset=0)
    page3, _ = _rows(client, s, limit=3, offset=6)
    assert total == 7 and len(page1) == 3 and len(page3) == 1
    assert client.get(f"{API}/finance/invoices", params={"limit": 5000}, headers=s.h).status_code == 422


def test_cancelled_invoices_are_hidden_unless_asked_and_never_counted(client, make_tenant, make_user, auth_headers):
    from sqlalchemy import text

    s = _school(client, make_tenant, make_user, auth_headers)
    _populate(client, s)
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        db.execute(text("UPDATE invoices SET status = 'cancelled' WHERE id = :i"), {"i": s.i_dan["id"]})
        db.commit()
    finally:
        db.close()
    assert _rows(client, s)[1] == 3
    rows, total = _rows(client, s, state="cancelled")
    assert total == 1 and rows[0]["state"] == "cancelled"
    assert client.get(f"{API}/finance/summary", headers=s.h).json()["due"] == 110000.0   # 30+30+50, sans les 20 000 annulés


# ======================= Synthèse =======================

def test_summary_totals_aging_and_by_class(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _populate(client, s)
    _inv(client, s, s.ada, 7000, TODAY - timedelta(days=5), label="Frais divers")             # échue depuis 5 j
    _inv(client, s, s.bao, 9000, TODAY - timedelta(days=75), label="Autre")                    # 61-90 j
    d = client.get(f"{API}/finance/summary", headers=s.h).json()
    assert d["academic_year"] == YEAR
    assert d["due"] == 146000.0 and d["paid"] == 60000.0 and d["outstanding"] == 86000.0
    assert d["recovery_rate_percent"] == round(100 * 60000 / 146000, 1)
    # En retard : Ada 20 000 (45 j) + 7 000 (5 j) + Dan 20 000 (100 j) + Bao 9 000 (75 j) = 56 000, 4 factures
    assert d["overdue_amount"] == 56000.0 and d["overdue_invoices"] == 4
    assert d["unpaid_invoices"] == 5                                                           # + Bao 30 000 à échoir
    assert d["aging"] == {"1-30 j": 7000.0, "31-60 j": 20000.0, "61-90 j": 9000.0, "plus de 90 j": 20000.0}
    assert sum(d["aging"].values()) == d["overdue_amount"]
    cls = {c["class_name"]: c for c in d["by_class"]}
    assert cls["6ème A"]["due"] == 76000.0 and cls["6ème A"]["paid"] == 10000.0 and cls["6ème A"]["students_with_balance"] == 2
    assert cls["5ème A"]["outstanding"] == 0.0 and cls["Sans classe"]["outstanding"] == 20000.0
    assert d["previous_years_outstanding"] == 0.0


def test_summary_boundaries_of_the_aging_buckets(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    for days, amount in ((0, 1000), (1, 10), (30, 20), (31, 40), (60, 80), (61, 160), (90, 320), (91, 640)):
        _inv(client, s, s.ada, amount, TODAY - timedelta(days=days), label=f"J-{days}")
    d = client.get(f"{API}/finance/summary", headers=s.h).json()
    assert d["aging"] == {"1-30 j": 30.0, "31-60 j": 120.0, "61-90 j": 480.0, "plus de 90 j": 640.0}   # J-0 n'est pas en retard
    assert d["overdue_amount"] == 1270.0


def test_summary_of_a_past_year_and_arrears(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _inv(client, s, s.ada, 8000, TODAY - timedelta(days=400), label="Ancien", year=PREV)
    _inv(client, s, s.ada, 3000, TODAY + timedelta(days=5))
    cur = client.get(f"{API}/finance/summary", headers=s.h).json()
    assert cur["due"] == 3000.0 and cur["previous_years_outstanding"] == 8000.0
    old = client.get(f"{API}/finance/summary", params={"academic_year": PREV}, headers=s.h).json()
    assert old["due"] == 8000.0 and old["overdue_amount"] == 8000.0


# ======================= Facturation d'une classe =======================

def _bulk(client, s, cls=None, dry=True, **over):
    body = {"class_id": (cls or s.c6)["id"], "label": "Scolarité T1", "amount_due": 25000, "due_date": str(TODAY + timedelta(days=30)), **over}
    return client.post(f"{API}/finance/bulk-invoices", params={"dry_run": str(dry).lower()}, json=body, headers=s.h)


def test_bulk_billing_previews_then_creates_one_invoice_per_active_student(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post(f"{API}/students/{s.bao['id']}/status", json={"status": "transferred", "reason": "Départ"}, headers=s.h)
    prev = _bulk(client, s).json()
    assert (prev["dry_run"], prev["students"], prev["created"], prev["total_amount"]) == (True, 1, 1, 25000.0)
    assert _rows(client, s)[1] == 0                                                            # rien d'écrit
    done = _bulk(client, s, dry=False).json()
    assert done["dry_run"] is False and done["created"] == 1
    rows, total = _rows(client, s)
    assert total == 1 and rows[0]["student_name"] == "ZOHOUN Ada" and rows[0]["amount_due"] == 25000.0 and rows[0]["academic_year"] == YEAR


def test_bulk_billing_is_replayable_without_duplicates_and_distinguishes_labels(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    assert _bulk(client, s, dry=False).json()["created"] == 2
    again = _bulk(client, s, dry=False).json()
    assert (again["created"], again["already_billed"]) == (0, 2)
    assert _rows(client, s)[1] == 2
    assert _bulk(client, s, dry=False, label="scolarité t1").json()["already_billed"] == 2      # casse ignorée
    assert _bulk(client, s, dry=False, label="Frais d'examen").json()["created"] == 2           # autre libellé : facturé
    s.late = _bulk(client, s, dry=False, label="Scolarité T1", academic_year=next_year(YEAR)).json()
    assert s.late["created"] == 2 and s.late["academic_year"] == next_year(YEAR)                # autre année : facturé


def test_two_simultaneous_bulk_runs_bill_each_student_once(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    codes = []
    threads = [threading.Thread(target=lambda: codes.append(_bulk(client, s, dry=False).status_code)) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert codes == [200] * 4
    assert _rows(client, s)[1] == 2


def test_bulk_billing_validation_and_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    assert _bulk(client, s, cls=other.c6).status_code == 404                                    # classe d'un autre établissement
    empty = client.post(f"{API}/classes", json={"name": "Vide", "level": "CP"}, headers=s.h).json()
    assert _bulk(client, s, cls=empty).status_code == 409
    for bad in ({"amount_due": 0}, {"amount_due": -5}, {"label": "ab"}, {"academic_year": "26-27"}):
        assert _bulk(client, s, **bad).status_code == 422, bad
    assert _bulk(client, s, academic_year=next_year(next_year(YEAR))).status_code == 422
    assert _rows(client, other)[1] == 0


def test_bulk_billing_is_audited_once(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _bulk(client, s, dry=False)
    _bulk(client, s, dry=False)                                                                 # rien de nouveau : pas de 2e entrée
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        logs = db.execute(select(AuditLog).where(AuditLog.action == "invoices.bulk_created")).scalars().all()
        assert len(logs) == 1 and logs[0].metadata_json["created"] == 2
    finally:
        db.close()


# ======================= Encaissements =======================

def test_payment_cannot_exceed_the_balance_or_hit_a_settled_invoice(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _inv(client, s, s.ada, 10000, TODAY)
    over = _pay(client, s, inv, 10001, expect=422)
    assert "dépasse le solde restant dû (10 000 F)" in over.json()["detail"]
    _pay(client, s, inv, 4000)
    assert "6 000 F" in _pay(client, s, inv, 6500, expect=422).json()["detail"]
    _pay(client, s, inv, 6000)                                                                  # solde exact : accepté
    assert "déjà soldée" in _pay(client, s, inv, 1, expect=409).json()["detail"]
    row = _rows(client, s)[0][0]
    assert row["amount_paid"] == 10000.0 and row["state"] == "paid"


def test_double_click_on_collect_records_a_single_payment(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _inv(client, s, s.ada, 10000, TODAY)
    codes = []
    pay = lambda: codes.append(client.post(f"{API}/payments", json={"invoice_id": inv["id"], "amount": 10000, "method": "cash"}, headers=s.h).status_code)
    threads = [threading.Thread(target=pay) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [201, 409, 409, 409, 409, 409], codes
    assert _rows(client, s)[0][0]["amount_paid"] == 10000.0


def test_every_payment_is_audited(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _inv(client, s, s.ada, 10000, TODAY)
    client.post(f"{API}/payments", json={"invoice_id": inv["id"], "amount": 2500, "method": "mobile_money", "reference": "MM-123"}, headers=s.acc_h)
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        log = db.execute(select(AuditLog).where(AuditLog.action == "payment.recorded")).scalar_one()
        assert log.actor_user_id == s.acc.id and log.target_id == inv["id"]
        assert log.metadata_json["amount"] == 2500.0 and log.metadata_json["reference"] == "MM-123" and log.metadata_json["balance_after"] == 7500.0
    finally:
        db.close()


# ======================= Droits =======================

def test_only_finance_roles_can_see_or_bill(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    for role in (UserRole.TEACHER, UserRole.STAFF, UserRole.CENSOR, UserRole.SUPERVISOR, UserRole.PARENT):
        u, pwd = make_user(tenant=s.tenant, role=role)
        h = auth_headers(u, pwd)
        assert client.get(f"{API}/finance/invoices", headers=h).status_code == 403, role
        assert client.get(f"{API}/finance/summary", headers=h).status_code == 403, role
        body = {"class_id": s.c6["id"], "label": "Scolarité", "amount_due": 1000, "due_date": str(TODAY)}
        assert client.post(f"{API}/finance/bulk-invoices", params={"dry_run": "false"}, json=body, headers=h).status_code == 403, role
    assert client.get(f"{API}/finance/invoices", headers=s.acc_h).status_code == 200
    f, fp = make_user(tenant=s.tenant, role=UserRole.FOUNDER)
    assert client.get(f"{API}/finance/summary", headers=auth_headers(f, fp)).status_code == 200


def test_bulk_billing_rebills_a_student_whose_invoice_was_cancelled(client, make_tenant, make_user, auth_headers):
    from sqlalchemy import text

    s = _school(client, make_tenant, make_user, auth_headers)
    _bulk(client, s, dry=False)
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        db.execute(text("UPDATE invoices SET status = 'cancelled' WHERE student_id = :i"), {"i": s.ada["id"]})
        db.commit()
    finally:
        db.close()
    again = _bulk(client, s, dry=False).json()
    assert (again["created"], again["already_billed"]) == (1, 1)
