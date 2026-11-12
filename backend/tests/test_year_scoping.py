"""AU-28 : factures et assiduité rattachées à l'année scolaire."""
from datetime import date

from app.models.user import UserRole
from app.services.academic_year_service import default_academic_year, next_year

API = "/api/v1"
YEAR = default_academic_year(date.today())
NEXT = next_year(YEAR)
Y0, Y1 = int(YEAR[:4]), int(NEXT[:4])
PREV = f"{Y0 - 1}-{Y0}"


def _school(client, make_tenant, make_user, auth_headers):
    class S:
        pass

    s = S()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    s.h = auth_headers(s.admin, pwd)
    s.cls = client.post(f"{API}/classes", json={"name": "Tle A", "level": "Tle"}, headers=s.h).json()
    s.stu = client.post(f"{API}/students", json={"first_name": "Ada", "last_name": "ZOHOUN", "class_id": s.cls["id"]}, headers=s.h).json()
    return s


def _invoice(client, s, amount, year=None, due=None, expect=201):
    body = {"student_id": s.stu["id"], "label": "Scolarité", "amount_due": amount, "due_date": due or f"{Y0}-10-01"}
    if year:
        body["academic_year"] = year
    r = client.post(f"{API}/invoices", json=body, headers=s.h)
    assert r.status_code == expect, r.text
    return r.json()


def _pay(client, s, invoice, amount):
    assert client.post(f"{API}/payments", json={"invoice_id": invoice["id"], "amount": amount, "method": "cash"}, headers=s.h).status_code == 201


def _set_cancelled(s, *invoice_ids):
    from sqlalchemy import text

    from app.db.session import SessionLocal, set_tenant_context

    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        for i in invoice_ids:
            db.execute(text("UPDATE invoices SET status = 'cancelled' WHERE id = :i"), {"i": i})
        db.commit()
    finally:
        db.close()


def _finance(client, s):
    return client.get(f"{API}/reports/overview", headers=s.h).json()["finance"]


def _close_year(client, s):
    plan = {"from_year": YEAR, "to_year": NEXT, "class_moves": [{"from_class_id": s.cls["id"], "to_class_id": None}], "repeater_student_ids": []}
    r = client.post(f"{API}/academic-year/rollover", params={"dry_run": "false"}, json=plan, headers=s.h)
    assert r.status_code == 200, r.text


# ======================= Factures =======================

def test_invoice_defaults_to_current_year_and_can_target_next_or_past_year(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    assert _invoice(client, s, 30000)["academic_year"] == YEAR
    assert _invoice(client, s, 5000, year=NEXT)["academic_year"] == NEXT            # réinscription facturée d'avance
    assert _invoice(client, s, 7000, year=PREV)["academic_year"] == PREV            # régularisation d'arriéré
    far = _invoice(client, s, 1000, year=next_year(NEXT), expect=422)               # faute de frappe : année lointaine
    assert "au plus" in far["detail"]
    bad = client.post(f"{API}/invoices", json={"student_id": s.stu["id"], "label": "x", "amount_due": 1, "due_date": f"{Y0}-10-01", "academic_year": "26-27"}, headers=s.h)
    assert bad.status_code == 422
    listed = client.get(f"{API}/students/{s.stu['id']}/invoices", headers=s.h).json()
    assert sorted(i["academic_year"] for i in listed) == sorted([YEAR, NEXT, PREV])


def test_report_separates_current_year_from_arrears_and_prebilled_year(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    cur = _invoice(client, s, 30000)
    _pay(client, s, cur, 10000)
    _invoice(client, s, 50000, year=NEXT)                       # ni dans l'année en cours, ni dans les arriérés
    old = _invoice(client, s, 20000, year=PREV)
    _pay(client, s, old, 5000)
    cancelled = _invoice(client, s, 99999, year=PREV)
    cancelled_now = _invoice(client, s, 88888)
    _set_cancelled(s, cancelled["id"], cancelled_now["id"])   # pas d'endpoint d'annulation : on simule l'état en base
    fin = _finance(client, s)
    assert (fin["amount_due_total"], fin["amount_paid_total"], fin["outstanding_total"]) == (30000.0, 10000.0, 20000.0)
    assert fin["previous_years_outstanding"] == 15000.0          # 20 000 - 5 000 ; la facture annulée est ignorée
    assert client.get(f"{API}/reports/overview", headers=s.h).json()["academic_year"] == YEAR


def test_after_rollover_unpaid_balance_becomes_arrears_and_stays_collectable(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    inv = _invoice(client, s, 30000)
    _pay(client, s, inv, 10000)
    preview = client.post(f"{API}/academic-year/rollover", params={"dry_run": "true"}, json={
        "from_year": YEAR, "to_year": NEXT, "class_moves": [{"from_class_id": s.cls["id"], "to_class_id": None}], "repeater_student_ids": []}, headers=s.h).json()
    assert any("20 000 F" in w and "arriérés" in w for w in preview["warnings"]), preview["warnings"]

    _close_year(client, s)
    fin = _finance(client, s)
    assert (fin["amount_due_total"], fin["outstanding_total"], fin["previous_years_outstanding"]) == (0.0, 0.0, 20000.0)
    _pay(client, s, inv, 20000)                                    # on peut encore encaisser l'ancienne facture
    assert _finance(client, s)["previous_years_outstanding"] == 0.0
    new = _invoice(client, s, 40000)
    assert new["academic_year"] == NEXT and _finance(client, s)["amount_due_total"] == 40000.0


def test_canteen_invoice_takes_the_year_of_its_month(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = client.post(f"{API}/canteen/plans", json={"name": "5j", "price_per_month": 15000}, headers=s.h).json()
    for month, expected in ((f"{Y0}-10", YEAR), (f"{Y1}-03", YEAR), (f"{Y1}-09", NEXT), (f"{Y0}-08", PREV)):
        sub = client.post(f"{API}/canteen/subscriptions", json={"student_id": s.stu["id"], "plan_id": plan["id"], "month": month}, headers=s.h)
        assert sub.status_code == 201, sub.text
        inv = next(i for i in client.get(f"{API}/students/{s.stu['id']}/invoices", headers=s.h).json() if i["id"] == sub.json()["invoice_id"])
        assert inv["academic_year"] == expected, month


# ======================= Assiduité =======================

def test_attendance_rate_covers_the_current_school_year_only(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)

    def mark(day, status):
        r = client.post(f"{API}/attendance", json={"student_id": s.stu["id"], "date": day, "status": status, "justified": False}, headers=s.h)
        assert r.status_code == 201, r.text

    mark(f"{Y0}-10-05", "present")
    mark(f"{Y0}-10-06", "absent")
    mark(f"{Y0 - 1}-10-06", "absent")        # année précédente : ne compte pas
    mark(f"{Y0}-08-31", "absent")            # la veille de la rentrée (31 août) : année précédente
    mark(f"{Y1}-09-01", "absent")            # lendemain de la fin de l'année : année suivante
    att = client.get(f"{API}/reports/overview", headers=s.h).json()["attendance"]
    assert (att["records_count"], att["unjustified_absences"], att["attendance_rate_percent"]) == (2, 1, 50.0)
    mark(f"{Y0}-09-01", "present")           # 1er septembre : première journée de l'année, incluse
    assert client.get(f"{API}/reports/overview", headers=s.h).json()["attendance"]["records_count"] == 3
    # La fiche de l'élève garde tout l'historique.
    assert len(client.get(f"{API}/students/{s.stu['id']}/attendance", headers=s.h).json()) == 6

    _close_year(client, s)
    after = client.get(f"{API}/reports/overview", headers=s.h).json()["attendance"]
    assert after["records_count"] == 1 and after["attendance_rate_percent"] == 0.0   # seul le 1er sept. suivant, absent


# ======================= Réseau =======================

def test_network_overview_uses_each_schools_own_year_and_reports_arrears(client, make_user, make_tenant, make_network, auth_headers):
    sup, sp = make_user(role=UserRole.SUPER_ADMIN)
    sh = auth_headers(sup, sp)
    network = make_network(name="Groupe")
    ta, tb = make_tenant(name="A"), make_tenant(name="B")
    for t in (ta, tb):
        client.post(f"{API}/networks/{network.id}/tenants/{t.id}", headers=sh)
    schools = []
    for t in (ta, tb):
        adm, pwd = make_user(tenant=t, role=UserRole.SCHOOL_ADMIN)
        h = auth_headers(adm, pwd)
        st = client.post(f"{API}/students", json={"first_name": "x", "last_name": "y"}, headers=h).json()
        schools.append((h, st))
    for (h, st), amt in zip(schools, (100000, 50000)):
        client.post(f"{API}/invoices", json={"student_id": st["id"], "label": "Sc", "amount_due": amt, "due_date": f"{Y0}-10-01"}, headers=h)
    # L'école A régularise un arriéré de l'année précédente.
    client.post(f"{API}/invoices", json={"student_id": schools[0][1]["id"], "label": "Arriéré", "amount_due": 12000, "due_date": f"{Y0}-01-10", "academic_year": PREV}, headers=schools[0][0])
    na, pn = make_user(network=network, role=UserRole.NETWORK_ADMIN)
    data = client.get(f"{API}/network/overview", headers=auth_headers(na, pn)).json()
    assert data["totals"]["revenue_due"] == 150000.0                      # l'arriéré n'entre pas dans le dû de l'année
    assert data["totals"]["previous_years_outstanding"] == 12000.0
    by = {x["name"]: x for x in data["schools"]}
    assert by["A"]["previous_years_outstanding"] == 12000.0 and by["B"]["previous_years_outstanding"] == 0
