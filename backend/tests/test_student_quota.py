"""AU-24 : limite d'élèves du plan d'abonnement."""
import threading
import uuid
from datetime import date

from app.models.user import UserRole
from app.services.academic_year_service import default_academic_year, next_year

API = "/api/v1"
HEADER = "Nom;Prénom;Classe;Matricule"


class School:
    pass


def _school(client, make_tenant, make_user, auth_headers, limit="none", name="École"):
    """limit : un entier (plan limité), None (plan illimité) ou "none" = aucun abonnement."""
    s = School()
    s.tenant = make_tenant(name=name)
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    s.h = auth_headers(s.admin, pwd)
    sup, sp = make_user(role=UserRole.SUPER_ADMIN)
    s.super_h = auth_headers(sup, sp)
    if limit != "none":
        plan = client.post(f"{API}/platform/plans", json={"name": f"Plan {limit}", "code": f"p-{uuid.uuid4().hex[:8]}", "price_per_month": 0, "max_students": limit}, headers=s.super_h)
        assert plan.status_code == 201, plan.text
        assert client.post(f"{API}/platform/tenants/{s.tenant.id}/subscription", headers=s.super_h).status_code == 201
        r = client.patch(f"{API}/platform/tenants/{s.tenant.id}/subscription", json={"plan_id": plan.json()["id"]}, headers=s.super_h)
        assert r.status_code == 200, r.text
    return s


def _add(client, s, n=1, prefix="E", expect=201):
    out = []
    for i in range(n):
        r = client.post(f"{API}/students", json={"first_name": f"{prefix}{i}", "last_name": "ELEVE"}, headers=s.h)
        assert r.status_code == expect, r.text
        out.append(r.json())
    return out


def _quota(client, s):
    return client.get(f"{API}/students/quota", headers=s.h).json()


def _csv(*rows):
    return ("\r\n".join([HEADER, *rows]) + "\r\n").encode("utf-8")


def _import(client, s, content, dry_run):
    return client.post(f"{API}/students/import", params={"dry_run": str(dry_run).lower()}, files={"file": ("e.csv", content)}, headers=s.h)


def _count(client, s):
    return int(client.get(f"{API}/students", headers=s.h).headers["X-Total-Count"])


# ======================= Création =======================

def test_creation_stops_at_the_plan_limit_with_a_clear_message(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=3)
    _add(client, s, 3)
    r = client.post(f"{API}/students", json={"first_name": "Trop", "last_name": "PLEIN"}, headers=s.h)
    assert r.status_code == 402
    d = r.json()["detail"]
    assert "3 élève(s) actif(s) sur 3" in d and "plan supérieur" in d
    assert _count(client, s) == 3
    assert _quota(client, s) == {"active_students": 3, "max_students": 3, "plan_name": "Plan 3", "remaining": 0}


def test_no_subscription_or_unlimited_plan_means_no_limit(client, make_tenant, make_user, auth_headers):
    free = _school(client, make_tenant, make_user, auth_headers, limit="none")
    _add(client, free, 4)
    assert _quota(client, free) == {"active_students": 4, "max_students": None, "plan_name": None, "remaining": None}
    unlimited = _school(client, make_tenant, make_user, auth_headers, limit=None)
    _add(client, unlimited, 4)
    q = _quota(client, unlimited)
    assert q["max_students"] is None and q["remaining"] is None and q["active_students"] == 4


def test_a_limit_below_one_is_refused_when_creating_a_plan(client, make_user, auth_headers):
    sup, sp = make_user(role=UserRole.SUPER_ADMIN)
    h = auth_headers(sup, sp)
    for bad in (0, -5):
        assert client.post(f"{API}/platform/plans", json={"name": "x", "code": f"c{abs(bad)}", "price_per_month": 0, "max_students": bad}, headers=h).status_code == 422


def test_each_school_is_counted_against_its_own_plan_only(client, make_tenant, make_user, auth_headers):
    a = _school(client, make_tenant, make_user, auth_headers, limit=1, name="A")
    b = _school(client, make_tenant, make_user, auth_headers, limit=5, name="B")
    _add(client, a, 1)
    _add(client, b, 3)
    assert client.post(f"{API}/students", json={"first_name": "x", "last_name": "y"}, headers=a.h).status_code == 402
    assert client.post(f"{API}/students", json={"first_name": "x", "last_name": "y"}, headers=b.h).status_code == 201


# ======================= Places libérées / réactivation =======================

def test_only_active_students_count_and_leaving_students_free_a_place(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=2)
    first, second = _add(client, s, 2)
    assert client.post(f"{API}/students", json={"first_name": "x", "last_name": "y"}, headers=s.h).status_code == 402
    for st, status_ in ((first, "transferred"), (second, "archived")):
        assert client.post(f"{API}/students/{st['id']}/status", json={"status": status_, "reason": "Départ"}, headers=s.h).status_code == 200
    assert _quota(client, s)["active_students"] == 0
    _add(client, s, 2, prefix="N")                                     # deux places libres
    assert client.post(f"{API}/students", json={"first_name": "x", "last_name": "y"}, headers=s.h).status_code == 402


def test_reactivating_a_student_needs_a_free_place(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=1)
    old, = _add(client, s, 1)
    client.post(f"{API}/students/{old['id']}/status", json={"status": "archived", "reason": "Fin de scolarité"}, headers=s.h)
    new, = _add(client, s, 1, prefix="N")
    r = client.post(f"{API}/students/{old['id']}/status", json={"status": "active", "reason": "Retour"}, headers=s.h)
    assert r.status_code == 402
    assert client.get(f"{API}/students/{old['id']}", headers=s.h).json()["status"] == "archived"   # inchangé
    client.post(f"{API}/students/{new['id']}/status", json={"status": "transferred", "reason": "Départ"}, headers=s.h)
    assert client.post(f"{API}/students/{old['id']}/status", json={"status": "active", "reason": "Retour"}, headers=s.h).status_code == 200


def test_lowering_the_plan_removes_nobody_but_blocks_new_students(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=5)
    _add(client, s, 4)
    small = client.post(f"{API}/platform/plans", json={"name": "Petit", "code": f"s-{uuid.uuid4().hex[:6]}", "price_per_month": 0, "max_students": 2}, headers=s.super_h).json()
    client.patch(f"{API}/platform/tenants/{s.tenant.id}/subscription", json={"plan_id": small["id"]}, headers=s.super_h)
    q = _quota(client, s)
    assert (q["active_students"], q["max_students"], q["remaining"]) == (4, 2, 0)
    assert _count(client, s) == 4
    assert client.post(f"{API}/students", json={"first_name": "x", "last_name": "y"}, headers=s.h).status_code == 402


def test_closing_the_year_frees_places_of_graduating_classes(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=2)
    cls = client.post(f"{API}/classes", json={"name": "Tle A", "level": "Tle"}, headers=s.h).json()
    for i in range(2):
        client.post(f"{API}/students", json={"first_name": f"T{i}", "last_name": "TERM", "class_id": cls["id"]}, headers=s.h)
    year = default_academic_year(date.today())
    plan = {"from_year": year, "to_year": next_year(year), "class_moves": [{"from_class_id": cls["id"], "to_class_id": None}], "repeater_student_ids": []}
    assert client.post(f"{API}/academic-year/rollover", params={"dry_run": "false"}, json=plan, headers=s.h).status_code == 200
    assert _quota(client, s)["active_students"] == 0
    _add(client, s, 2, prefix="N")


# ======================= Import =======================

def test_import_over_the_limit_is_refused_in_preview_and_commit_and_writes_nothing(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=3)
    _add(client, s, 1)
    big = _csv("A;a;;", "B;b;;", "C;c;;")                      # 1 existant + 3 = 4 > 3
    for dry in (True, False):
        r = _import(client, s, big, dry)
        assert r.status_code == 402, (dry, r.text)
        assert "il reste 2 place(s) alors que 3 sont demandées" in r.json()["detail"]
    assert _count(client, s) == 1


def test_import_filling_the_plan_exactly_is_accepted_then_the_next_one_is_refused(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=3)
    _add(client, s, 1)
    assert _import(client, s, _csv("A;a;;", "B;b;;"), True).status_code == 200
    assert _import(client, s, _csv("A;a;;", "B;b;;"), False).status_code == 200
    assert _count(client, s) == 3
    assert _import(client, s, _csv("Z;z;;"), False).status_code == 402


def test_row_errors_are_reported_before_the_quota_is_checked(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=1)
    r = _import(client, s, _csv(";sans nom;;", "B;b;;", "C;c;;"), True)       # 2 valides > 1, mais une ligne est en erreur
    assert r.status_code == 200 and r.json()["error_count"] == 1


# ======================= Concurrence =======================

def test_simultaneous_registrations_cannot_exceed_the_limit(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=3)
    codes: list[int] = []

    def go(i):
        r = client.post(f"{API}/students", json={"first_name": f"P{i}", "last_name": "PARALLELE"}, headers=s.h)
        codes.append(r.status_code)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [201, 201, 201] + [402] * 5, codes
    assert _quota(client, s)["active_students"] == 3


# ======================= Lecture du quota =======================

def test_quota_is_readable_by_registry_staff_only(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers, limit=10)
    for role, ok in ((UserRole.TEACHER, True), (UserRole.STAFF, True), (UserRole.ACCOUNTANT, True), (UserRole.PARENT, False)):
        u, pwd = make_user(tenant=s.tenant, role=role)
        assert (client.get(f"{API}/students/quota", headers=auth_headers(u, pwd)).status_code == 200) is ok, role
