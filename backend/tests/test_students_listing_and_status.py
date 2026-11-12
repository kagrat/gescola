"""AU-08 (pagination/recherche serveur) et AU-23 (statut d'élève)."""
from app.models.user import UserRole

API = "/api/v1"


def _school(client, make_tenant, make_user, auth_headers):
    class S:
        pass

    s = S()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    s.admin_h = auth_headers(s.admin, pwd)
    s.cls = client.post(f"{API}/classes", json={"name": "6ème A", "level": "6ème"}, headers=s.admin_h).json()
    s.cls2 = client.post(f"{API}/classes", json={"name": "5ème B", "level": "5ème"}, headers=s.admin_h).json()
    return s


def _mk(client, h, first, last, class_id=None, matricule=None):
    body = {"first_name": first, "last_name": last, "class_id": class_id, "matricule": matricule}
    r = client.post(f"{API}/students", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


# ======================= Pagination =======================

def test_pages_are_disjoint_complete_and_stably_ordered(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    # Homonymes volontaires : sans critère final (id), l'ordre entre eux serait indéterminé.
    names = [("Aya", "Diallo"), ("Aya", "Diallo"), ("Koffi", "Mensah"), ("Zoé", "Autre"), ("Awa", "Bello"),
             ("Jean", "Kakpo"), ("Jean", "Kakpo")]
    created = {_mk(client, s.admin_h, f, l)["id"] for f, l in names}

    seen, ordered = [], []
    for offset in (0, 3, 6):
        r = client.get(f"{API}/students", params={"limit": 3, "offset": offset}, headers=s.admin_h)
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "7"
        ordered += [(x["last_name"], x["first_name"]) for x in r.json()]
        seen += [x["id"] for x in r.json()]
    assert len(seen) == 7 and set(seen) == created            # aucune perte, aucun doublon entre pages
    assert ordered == sorted(ordered, key=lambda t: (t[0].lower(), t[1].lower()))
    again = [x["id"] for x in client.get(f"{API}/students", params={"limit": 3, "offset": 3}, headers=s.admin_h).json()]
    assert again == seen[3:6]                                  # même page = même contenu, à chaque appel

    beyond = client.get(f"{API}/students", params={"limit": 3, "offset": 100}, headers=s.admin_h)
    assert beyond.status_code == 200 and beyond.json() == [] and beyond.headers["X-Total-Count"] == "7"


def test_page_size_is_always_bounded(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    assert client.get(f"{API}/students", params={"limit": 501}, headers=s.admin_h).status_code == 422
    assert client.get(f"{API}/students", params={"limit": 0}, headers=s.admin_h).status_code == 422
    assert client.get(f"{API}/students", params={"offset": -1}, headers=s.admin_h).status_code == 422
    assert client.get(f"{API}/students", params={"limit": 500}, headers=s.admin_h).status_code == 200


# ======================= Recherche =======================

def test_search_matches_any_order_case_and_matricule(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    jean = _mk(client, s.admin_h, "Jean", "Kakpo", matricule="MAT-0042")
    _mk(client, s.admin_h, "Aya", "Diallo")

    def ids(q):
        r = client.get(f"{API}/students", params={"q": q}, headers=s.admin_h)
        assert r.status_code == 200
        return [x["id"] for x in r.json()], int(r.headers["X-Total-Count"])

    assert ids("kakpo jean") == ([jean["id"]], 1)      # ordre des mots indifférent
    assert ids("KAK") == ([jean["id"]], 1)             # sous-chaîne, casse indifférente
    assert ids("mat-0042") == ([jean["id"]], 1)        # matricule
    assert ids("jean diallo") == ([], 0)               # chaque mot doit correspondre au même élève
    assert ids("   ")[1] == 2                          # recherche vide = pas de filtre


def test_search_treats_wildcards_literally(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    _mk(client, s.admin_h, "Jean", "Kakpo")
    _mk(client, s.admin_h, "Aya", "Diallo")
    for hostile in ("%", "_", "%%", "J_an", "\\"):
        r = client.get(f"{API}/students", params={"q": hostile}, headers=s.admin_h)
        assert r.status_code == 200 and r.headers["X-Total-Count"] == "0", hostile


def test_filters_by_class_unassigned_and_status(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    a = _mk(client, s.admin_h, "A", "Un", s.cls["id"])
    b = _mk(client, s.admin_h, "B", "Deux", s.cls2["id"])
    c = _mk(client, s.admin_h, "C", "Trois")
    assert client.post(f"{API}/students/{b['id']}/status", json={"status": "transferred", "reason": "Déménagement"}, headers=s.admin_h).status_code == 200

    def got(**params):
        return {x["id"] for x in client.get(f"{API}/students", params=params, headers=s.admin_h).json()}

    assert got(class_id=s.cls["id"]) == {a["id"]}
    assert got(unassigned="true") == {c["id"]}
    assert got(status="active") == {a["id"], c["id"]}
    assert got(status="transferred") == {b["id"]}
    assert got(class_id=s.cls2["id"], status="active") == set()
    assert client.get(f"{API}/students", params={"status": "inconnu"}, headers=s.admin_h).status_code == 422


def test_search_never_crosses_establishments(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    mine = _mk(client, s.admin_h, "Jean", "Kakpo")
    _mk(client, other.admin_h, "Jean", "Kakpo")
    r = client.get(f"{API}/students", params={"q": "kakpo"}, headers=s.admin_h)
    assert [x["id"] for x in r.json()] == [mine["id"]] and r.headers["X-Total-Count"] == "1"
    assert client.get(f"{API}/students", headers=other.admin_h).headers["X-Total-Count"] == "1"


def test_cors_exposes_the_total_header(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    from app.core.config import get_settings
    origin = get_settings().CORS_ALLOWED_ORIGINS[0]
    r = client.get(f"{API}/students", headers={**s.admin_h, "Origin": origin})
    assert "x-total-count" in r.headers.get("access-control-expose-headers", "").lower()


# ======================= Statut =======================

def _audit(client, h, action="student.status_changed"):
    return [a for a in client.get(f"{API}/audit-logs", headers=h).json() if a["action"] == action]


def test_status_change_is_audited_with_reason(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    kid = _mk(client, s.admin_h, "Jean", "Kakpo", s.cls["id"])
    r = client.post(f"{API}/students/{kid['id']}/status", json={"status": "transferred", "reason": "  Transfert vers Lomé  "}, headers=s.admin_h)
    assert r.status_code == 200 and r.json()["status"] == "transferred"
    assert r.json()["class_id"] == s.cls["id"]                       # la classe d'origine est conservée
    (entry,) = _audit(client, s.admin_h)
    assert entry["target_id"] == kid["id"] and entry["actor_user_id"] == str(s.admin.id)
    assert entry["metadata_json"]["from"] == "active" and entry["metadata_json"]["to"] == "transferred"
    assert entry["metadata_json"]["reason"] == "Transfert vers Lomé"  # motif nettoyé


def test_status_change_requires_a_real_reason_and_a_real_change(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    kid = _mk(client, s.admin_h, "Jean", "Kakpo")
    url = f"{API}/students/{kid['id']}/status"
    assert client.post(url, json={"status": "archived"}, headers=s.admin_h).status_code == 422
    assert client.post(url, json={"status": "archived", "reason": ""}, headers=s.admin_h).status_code == 422
    assert client.post(url, json={"status": "archived", "reason": "  ab  "}, headers=s.admin_h).status_code == 422
    assert client.post(url, json={"status": "archived", "reason": "x" * 501}, headers=s.admin_h).status_code == 422
    assert client.post(url, json={"status": "bizarre", "reason": "motif valable"}, headers=s.admin_h).status_code == 422
    same = client.post(url, json={"status": "active", "reason": "motif valable"}, headers=s.admin_h)
    assert same.status_code == 409
    assert _audit(client, s.admin_h) == []                           # aucun changement = aucune trace
    assert client.get(f"{API}/students/{kid['id']}", headers=s.admin_h).json()["status"] == "active"


def test_generic_patch_cannot_change_status_silently(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    kid = _mk(client, s.admin_h, "Jean", "Kakpo")
    r = client.patch(f"{API}/students/{kid['id']}", json={"status": "archived"}, headers=s.admin_h)
    assert r.status_code == 422
    assert client.get(f"{API}/students/{kid['id']}", headers=s.admin_h).json()["status"] == "active"
    ok = client.patch(f"{API}/students/{kid['id']}", json={"first_name": "Jeanne"}, headers=s.admin_h)
    assert ok.status_code == 200 and ok.json()["first_name"] == "Jeanne"


def test_only_registry_managers_change_status_and_never_across_schools(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)
    kid = _mk(client, s.admin_h, "Jean", "Kakpo")
    url = f"{API}/students/{kid['id']}/status"
    body = {"status": "archived", "reason": "motif valable"}
    for role in (UserRole.TEACHER, UserRole.CENSOR, UserRole.SUPERVISOR, UserRole.ACCOUNTANT, UserRole.PARENT):
        user, pwd = make_user(tenant=s.tenant, role=role)
        assert client.post(url, json=body, headers=auth_headers(user, pwd)).status_code == 403, role
    assert client.post(url, json=body, headers=other.admin_h).status_code == 404   # jamais 403 : pas de confirmation d'existence
    staff, pwd = make_user(tenant=s.tenant, role=UserRole.STAFF)
    assert client.post(url, json=body, headers=auth_headers(staff, pwd)).status_code == 200
    assert len(_audit(client, s.admin_h)) == 1


def test_inactive_students_leave_rosters_and_come_back_on_reactivation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    stay = _mk(client, s.admin_h, "Reste", "Là", s.cls["id"])
    leave = _mk(client, s.admin_h, "Part", "Ailleurs", s.cls["id"])

    def roster():
        r = client.get(f"{API}/classes/{s.cls['id']}/attendance", params={"date": "2026-10-05"}, headers=s.admin_h)
        assert r.status_code == 200
        return {x["student_id"] for x in r.json()}

    assert roster() == {stay["id"], leave["id"]}
    client.post(f"{API}/students/{leave['id']}/status", json={"status": "graduated", "reason": "Fin de cycle"}, headers=s.admin_h)
    assert roster() == {stay["id"]}
    client.post(f"{API}/students/{leave['id']}/status", json={"status": "active", "reason": "Erreur de saisie"}, headers=s.admin_h)
    assert roster() == {stay["id"], leave["id"]}
    assert len(_audit(client, s.admin_h)) == 2
