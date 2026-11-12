"""CP-01 : barèmes de frais par niveau, tranches datées, remises par élève."""
from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal, set_tenant_context
from app.models.audit import AuditLog
from app.models.user import UserRole
from app.services.academic_year_service import default_academic_year, next_year
from app.services.fee_plan_service import discounted, due_date_for

API = "/api/v1"
YEAR = default_academic_year(date.today())
START = int(YEAR[:4])


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
    s.cls = client.post(f"{API}/classes", json={"name": "6ème A", "level": "6ème"}, headers=s.h).json()
    mk_st = lambda f, l: client.post(f"{API}/students", json={"first_name": f, "last_name": l, "class_id": s.cls["id"]}, headers=s.h).json()
    s.ada, s.bao = mk_st("Ada", "ZOHOUN"), mk_st("Bao", "AGBO")
    return s


PLAN = {"level": "6ème", "name": "Scolarité", "installments": [
    {"label": "Tranche 1", "amount": 50000, "month": 10, "day": 15},
    {"label": "Tranche 2", "amount": 30000, "month": 1, "day": 10},
    {"label": "Tranche 3", "amount": 20000, "month": 4, "day": 5},
]}


def _plan(client, s, **over):
    r = client.post(f"{API}/finance/fee-plans", json={**PLAN, **over}, headers=s.acc_h)
    assert r.status_code == 201, r.text
    return r.json()


def _apply(client, s, plan, dry=True, cls=None, headers=None, **over):
    return client.post(f"{API}/finance/fee-plans/{plan['id']}/apply", params={"dry_run": str(dry).lower()},
                       json={"class_id": (cls or s.cls)["id"], **over}, headers=headers or s.acc_h)


def _invoices(client, s):
    r = client.get(f"{API}/finance/invoices", params={"limit": 200}, headers=s.h)
    return r.json()


# ---------- pur calcul ----------

def test_rounding_and_due_dates():
    assert discounted(50000, 25) == 37500.0 and discounted(10005, 50) == 5003.0       # demi-franc : arrondi vers le haut
    assert discounted(33333, 15) == 28333.0 and discounted(1000, 100) == 0.0 and discounted(1000, 0) == 1000.0
    assert due_date_for("2026-2027", 10, 15) == date(2026, 10, 15) and due_date_for("2026-2027", 1, 10) == date(2027, 1, 10)
    assert due_date_for("2026-2027", 8, 31 - 3) == date(2027, 8, 28) and due_date_for("2026-2027", 9, 1) == date(2026, 9, 1)


# ---------- barèmes ----------

def test_plan_crud_orders_installments_in_school_year_order(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    shuffled = {**PLAN, "installments": list(reversed(PLAN["installments"]))}
    p = _plan(client, s, **shuffled)
    assert [i["label"] for i in p["installments"]] == ["Tranche 1", "Tranche 2", "Tranche 3"] and p["total"] == 100000.0
    assert client.post(f"{API}/finance/fee-plans", json=PLAN, headers=s.h).status_code == 409           # même niveau + même nom
    assert client.post(f"{API}/finance/fee-plans", json={**PLAN, "level": "5ème"}, headers=s.h).status_code == 201
    upd = client.put(f"{API}/finance/fee-plans/{p['id']}", json={**PLAN, "installments": PLAN["installments"][:1]}, headers=s.h)
    assert upd.status_code == 200 and upd.json()["total"] == 50000.0
    assert len(client.get(f"{API}/finance/fee-plans", headers=s.h).json()) == 2
    assert client.delete(f"{API}/finance/fee-plans/{p['id']}", headers=s.h).status_code == 204
    assert client.delete(f"{API}/finance/fee-plans/{p['id']}", headers=s.h).status_code == 404


def test_plan_validation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    one = PLAN["installments"][0]
    bad = [
        {"installments": []},
        {"installments": [one, {**one}]},                                   # libellés en double
        {"installments": [{**one, "month": 13}]}, {"installments": [{**one, "day": 29}]},
        {"installments": [{**one, "amount": 0}]}, {"installments": [{**one, "amount": -5}]},
        {"installments": [{**one, "label": f"T{i}"} for i in range(13)]},   # plus de 12 tranches
        {"name": "ab"}, {"level": ""},
    ]
    for over in bad:
        assert client.post(f"{API}/finance/fee-plans", json={**PLAN, **over}, headers=s.h).status_code == 422, over


def test_plan_roles_and_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    for h in (s.staff_h, s.teacher_h):
        assert client.get(f"{API}/finance/fee-plans", headers=h).status_code == 403
        assert client.post(f"{API}/finance/fee-plans", json=PLAN, headers=h).status_code == 403
        assert _apply(client, s, plan, headers=h).status_code == 403
    assert client.get(f"{API}/finance/fee-plans", headers=other.h).json() == []
    assert client.put(f"{API}/finance/fee-plans/{plan['id']}", json=PLAN, headers=other.h).status_code == 404
    assert client.delete(f"{API}/finance/fee-plans/{plan['id']}", headers=other.h).status_code == 404
    assert _apply(client, s, plan, headers=other.h, cls=other.cls).status_code == 404
    assert _apply(client, other, plan, headers=other.h).status_code == 404       # classe d'un autre établissement + barème d'un autre


# ---------- application à une classe ----------

def test_apply_previews_then_creates_one_invoice_per_student_and_installment(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    prev = _apply(client, s, plan).json()
    assert prev["dry_run"] is True and prev["students"] == 2 and prev["total_amount"] == 200000.0
    assert [(i["label"], i["created"], i["total_amount"]) for i in prev["installments"]] == [
        ("Scolarité – Tranche 1", 2, 100000.0), ("Scolarité – Tranche 2", 2, 60000.0), ("Scolarité – Tranche 3", 2, 40000.0)]
    assert _invoices(client, s) == []                                                  # aperçu : rien d'écrit
    done = _apply(client, s, plan, dry=False).json()
    assert done["dry_run"] is False and done["total_amount"] == 200000.0
    rows = _invoices(client, s)
    assert len(rows) == 6 and {r["academic_year"] for r in rows} == {YEAR}
    t1 = next(r for r in rows if r["label"].endswith("Tranche 1") and r["student_name"] == "ZOHOUN Ada")
    t2 = next(r for r in rows if r["label"].endswith("Tranche 2") and r["student_name"] == "ZOHOUN Ada")
    assert (t1["due_date"], t1["amount_due"]) == (f"{START}-10-15", 50000.0) and t2["due_date"] == f"{START + 1}-01-10"


def test_apply_is_replayable_and_picks_up_new_installments_only(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    _apply(client, s, plan, dry=False)
    again = _apply(client, s, plan, dry=False).json()
    assert sum(i["created"] for i in again["installments"]) == 0 and sum(i["already_billed"] for i in again["installments"]) == 6
    assert len(_invoices(client, s)) == 6
    extra = {**PLAN, "installments": PLAN["installments"] + [{"label": "Tranche 4", "amount": 10000, "month": 6, "day": 1}]}
    client.put(f"{API}/finance/fee-plans/{plan['id']}", json=extra, headers=s.h)
    third = _apply(client, s, plan, dry=False).json()
    assert [i["created"] for i in third["installments"]] == [0, 0, 0, 2] and len(_invoices(client, s)) == 8
    nxt = _apply(client, s, plan, dry=False, academic_year=next_year(YEAR)).json()    # année suivante : refacturée
    assert nxt["academic_year"] == next_year(YEAR) and sum(i["created"] for i in nxt["installments"]) == 8


def test_apply_guards(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    cm2 = client.post(f"{API}/classes", json={"name": "5ème A", "level": "5ème"}, headers=s.h).json()
    r = _apply(client, s, plan, cls=cm2)
    assert r.status_code == 422 and "6ème" in r.json()["detail"]                           # mauvais niveau
    empty = client.post(f"{API}/classes", json={"name": "6ème B", "level": "6ème"}, headers=s.h).json()
    assert _apply(client, s, plan, cls=empty).status_code == 409
    assert _apply(client, s, plan, academic_year=next_year(next_year(YEAR))).status_code == 422
    assert _apply(client, s, plan, academic_year="26-27").status_code == 422
    client.post(f"{API}/students/{s.bao['id']}/status", json={"status": "transferred", "reason": "Départ"}, headers=s.h)
    assert _apply(client, s, plan).json()["students"] == 1                                  # seuls les actifs


def test_apply_is_audited_once(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    _apply(client, s, plan, dry=False)
    _apply(client, s, plan, dry=False)
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        rows = db.execute(select(AuditLog).where(AuditLog.action.like("fee_plan.%"))).scalars().all()
        assert sorted(r.action for r in rows) == ["fee_plan.applied", "fee_plan.created"]
        applied = next(r for r in rows if r.action == "fee_plan.applied")
        assert applied.metadata_json["created"] == 6 and applied.metadata_json["total"] == 200000.0
    finally:
        db.close()


# ---------- remises ----------

def test_student_discount_is_applied_with_rounding_and_exemption(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    r = client.put(f"{API}/students/{s.ada['id']}/fee-discount", json={"percent": 25, "reason": "Fratrie"}, headers=s.acc_h)
    assert r.status_code == 200 and r.json()["fee_discount_percent"] == 25.0 and r.json()["fee_discount_reason"] == "Fratrie"
    prev = _apply(client, s, plan).json()
    assert prev["discounted_students"] == 1 and prev["exempted_students"] == 0
    assert prev["installments"][0]["total_amount"] == 37500.0 + 50000.0                     # Ada -25 %, Bao plein tarif
    _apply(client, s, plan, dry=False)
    ada = [r for r in _invoices(client, s) if r["student_name"] == "ZOHOUN Ada"]
    assert sorted(r["amount_due"] for r in ada) == [15000.0, 22500.0, 37500.0]
    # Bourse complète : aucune facture pour cet élève
    client.put(f"{API}/students/{s.bao['id']}/fee-discount", json={"percent": 100, "reason": "Bourse"}, headers=s.h)
    ex = client.post(f"{API}/students", json={"first_name": "Cléo", "last_name": "DOSSOU", "class_id": s.cls["id"]}, headers=s.h).json()
    client.put(f"{API}/students/{ex['id']}/fee-discount", json={"percent": 100}, headers=s.h)
    rep = _apply(client, s, plan, dry=False).json()
    assert rep["exempted_students"] == 2 and sum(i["created"] for i in rep["installments"]) == 0   # Ada, Bao déjà facturés ; Cléo exemptée
    assert all(r["student_name"] != "DOSSOU Cléo" for r in _invoices(client, s))


def test_changing_a_discount_never_rewrites_existing_invoices(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    _apply(client, s, plan, dry=False)
    client.put(f"{API}/students/{s.ada['id']}/fee-discount", json={"percent": 50}, headers=s.h)
    assert sorted(r["amount_due"] for r in _invoices(client, s) if r["student_name"] == "ZOHOUN Ada") == [20000.0, 30000.0, 50000.0]


def test_discount_validation_audit_and_access(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    url = f"{API}/students/{s.ada['id']}/fee-discount"
    for bad in (101, -1):
        assert client.put(url, json={"percent": bad}, headers=s.h).status_code == 422
    assert client.put(url, json={"percent": 10, "reason": "x" * 201}, headers=s.h).status_code == 422
    for h in (s.staff_h, s.teacher_h):
        assert client.put(url, json={"percent": 10}, headers=h).status_code == 403
    assert client.put(url, json={"percent": 10}, headers=other.h).status_code == 404
    client.put(url, json={"percent": 30, "reason": "Fratrie"}, headers=s.h)
    cleared = client.put(url, json={"percent": 0, "reason": "ignoré"}, headers=s.h).json()
    assert cleared["fee_discount_percent"] == 0.0 and cleared["fee_discount_reason"] is None          # pas de motif sans remise
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        logs = db.execute(select(AuditLog).where(AuditLog.action == "student.fee_discount_set").order_by(AuditLog.created_at)).scalars().all()
        assert [(l.metadata_json["from"], l.metadata_json["to"]) for l in logs] == [(0.0, 30.0), (30.0, 0.0)]
    finally:
        db.close()


def test_apply_refuses_oversized_classes(client, make_tenant, make_user, auth_headers, monkeypatch):
    from app.services import fee_plan_service

    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(client, s)
    monkeypatch.setattr(fee_plan_service, "MAX_STUDENTS", 1)
    assert _apply(client, s, plan).status_code == 413
