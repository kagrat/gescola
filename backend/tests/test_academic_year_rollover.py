"""AU-07 : passage d'année scolaire."""
import threading
import uuid
from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal, set_tenant_context
from app.models.audit import AuditLog
from app.models.enrollment import StudentEnrollment
from app.models.user import UserRole
from app.models.academic import SchoolClass
from app.services.academic_year_service import default_academic_year, next_year
from app.services.rollover_service import normalize_level, suggest_destination

API = "/api/v1"
YEAR = default_academic_year(date.today())
NEXT = next_year(YEAR)


class School:
    pass


def _school(client, make_tenant, make_user, auth_headers) -> School:
    """6ème A (Ada 15, Bao 6) · 5ème A (Cléo 12) · 4ème A (vide) · Tle A (Dan 13, Eve 4)."""
    s = School()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    s.h = auth_headers(s.admin, pwd)
    mk = lambda name, level: client.post(f"{API}/classes", json={"name": name, "level": level}, headers=s.h).json()
    s.c6, s.c5, s.c4, s.ct = mk("6ème A", "6ème"), mk("5ème A", "5ème"), mk("4ème A", "4ème"), mk("Tle A", "Tle")
    s.maths = client.post(f"{API}/subjects", json={"name": "Maths", "default_coefficient": 1}, headers=s.h).json()

    def student(first, last, cls, avg):
        st = client.post(f"{API}/students", json={"first_name": first, "last_name": last, "class_id": cls["id"]}, headers=s.h).json()
        for term in ("T1", "T2", "T3"):
            r = client.post(f"{API}/grades", json={"student_id": st["id"], "subject_id": s.maths["id"], "term": term,
                                                  "evaluation_label": "D1", "value": avg}, headers=s.h)
            assert r.status_code == 201, r.text
        return st

    s.ada, s.bao = student("Ada", "ZOHOUN", s.c6, 15), student("Bao", "AGBO", s.c6, 6)
    s.cleo = student("Cléo", "DOSSOU", s.c5, 12)
    s.dan, s.eve = student("Dan", "FADO", s.ct, 13), student("Eve", "GBEDO", s.ct, 4)
    s.teacher, tpwd = make_user(tenant=s.tenant, role=UserRole.TEACHER)
    s.teacher_h = auth_headers(s.teacher, tpwd)
    return s


def _plan(s, *, repeaters=(), moves=None):
    return {
        "from_year": YEAR, "to_year": NEXT,
        "class_moves": moves if moves is not None else [
            {"from_class_id": s.c6["id"], "to_class_id": s.c5["id"]},
            {"from_class_id": s.c5["id"], "to_class_id": s.c4["id"]},
            {"from_class_id": s.ct["id"], "to_class_id": None},
        ],
        "repeater_student_ids": [r["id"] for r in repeaters],
    }


def _rollover(client, s, plan, dry_run=True, headers=None):
    return client.post(f"{API}/academic-year/rollover", params={"dry_run": str(dry_run).lower()}, json=plan,
                       headers=headers or s.h)


def _get(client, s, st):
    return client.get(f"{API}/students/{st['id']}", headers=s.h).json()


# ======================= Pures =======================

def test_level_names_are_understood_and_destination_suggested():
    assert [normalize_level(x) for x in ("6ème", "6eme", "6e", "5ème", "2nde", "Seconde", "1ère", "1ere", "Tle", "Terminale", "CM2", "ce1")] == \
           ["6e", "6e", "6e", "5e", "2nde", "2nde", "1ere", "1ere", "tle", "tle", "cm2", "ce1"]
    assert normalize_level("Maternelle 1") is None and normalize_level("") is None

    def c(name, level):
        return SchoolClass(id=uuid.uuid4(), name=name, level=level)

    a6, b6, a5, b5, tle, odd = c("6ème A", "6ème"), c("6ème B", "6ème"), c("5ème A", "5ème"), c("5ème B", "5ème"), c("Tle D", "Tle"), c("Éveil", "Maternelle")
    everyone = [a6, b6, a5, b5, tle, odd]
    assert suggest_destination(a6, everyone) == (a5.id, False)      # même lettre
    assert suggest_destination(b6, everyone) == (b5.id, False)
    assert suggest_destination(tle, everyone) == (None, True)      # terminale
    assert suggest_destination(odd, everyone) == (None, False)     # niveau inconnu : la Direction choisit
    assert suggest_destination(a5, [a5, b5]) == (None, False)      # pas de classe supérieure : pas de devinette
    assert suggest_destination(a6, [a6, a5]) == (a5.id, False)     # une seule candidate


# ======================= Proposition =======================

def test_proposal_suggests_destinations_and_flags_students_below_pass_mark(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    body = client.get(f"{API}/academic-year/proposal", headers=s.h).json()
    assert body["current_year"] == YEAR and body["next_year"] == NEXT
    rows = {r["name"]: r for r in body["classes"]}
    assert set(rows) == {"6ème A", "5ème A", "Tle A"}  # 4ème A est vide : sans objet
    assert rows["6ème A"]["suggested_to_class_id"] == s.c5["id"]
    assert rows["5ème A"]["suggested_to_class_id"] == s.c4["id"]
    assert rows["Tle A"]["suggested_graduate"] is True
    assert [(x["name"], x["annual_average"]) for x in rows["6ème A"]["at_risk"]] == [("Bao AGBO", 6.0)]
    assert [x["name"] for x in rows["Tle A"]["at_risk"]] == ["Eve GBEDO"]
    assert rows["5ème A"]["at_risk"] == []
    low = client.get(f"{API}/academic-year/proposal", params={"pass_mark": 14}, headers=s.h).json()
    assert {x["name"] for r in low["classes"] if r["name"] == "6ème A" for x in r["at_risk"]} == {"Bao AGBO"}
    assert {x["name"] for r in low["classes"] if r["name"] == "5ème A" for x in r["at_risk"]} == {"Cléo DOSSOU"}


# ======================= Aperçu =======================

def test_preview_reports_everything_and_writes_nothing(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    r = _rollover(client, s, _plan(s, repeaters=[s.bao, s.eve]))
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["dry_run"] is True and rep["executed"] is False and rep["errors"] == []
    assert (rep["promoted"], rep["repeated"], rep["graduated"]) == (2, 2, 1)
    by = {c["from_class"]: c for c in rep["classes"]}
    assert (by["6ème A"]["promoted"], by["6ème A"]["repeated"], by["6ème A"]["to_class"]) == (1, 1, "5ème A")
    assert by["Tle A"]["to_class"] is None and by["Tle A"]["graduated"] == 1 and by["Tle A"]["repeated"] == 1
    # Rien n'a bougé.
    assert _get(client, s, s.ada)["class_id"] == s.c6["id"] and _get(client, s, s.dan)["status"] == "active"
    assert client.get(f"{API}/establishment/settings", headers=s.h).json()["academic_year"] == YEAR
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        assert db.execute(select(StudentEnrollment)).first() is None
        assert db.execute(select(AuditLog).where(AuditLog.action == "academic_year.rolled_over")).first() is None
    finally:
        db.close()


def test_preview_warns_about_unlocked_grades_and_merged_classes(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(s, moves=[
        {"from_class_id": s.c6["id"], "to_class_id": s.c4["id"]},
        {"from_class_id": s.c5["id"], "to_class_id": s.c4["id"]},
        {"from_class_id": s.ct["id"], "to_class_id": None},
    ])
    rep = _rollover(client, s, plan).json()
    assert rep["errors"] == []
    text = " ".join(rep["warnings"])
    assert "ne sont pas verrouillées" in text and "regroupées dans « 4ème A »" in text


# ======================= Exécution =======================

def test_rollover_moves_everyone_exactly_once_even_with_chained_classes(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.patch(f"{API}/establishment/settings", json={"term_periods": {"T1": {"start": "2026-09-01", "end": "2026-12-15"}}}, headers=s.h)
    r = _rollover(client, s, _plan(s, repeaters=[s.bao, s.eve]), dry_run=False)
    assert r.status_code == 200, r.text
    assert r.json()["executed"] is True

    ada, bao, cleo, dan, eve = (_get(client, s, x) for x in (s.ada, s.bao, s.cleo, s.dan, s.eve))
    assert ada["class_id"] == s.c5["id"] and ada["is_repeater"] is False       # 6e → 5e (et PAS 4e)
    assert cleo["class_id"] == s.c4["id"]                                        # 5e → 4e
    assert bao["class_id"] == s.c6["id"] and bao["is_repeater"] is True          # redouble
    assert dan["status"] == "graduated" and dan["class_id"] == s.ct["id"]        # sortant, classe conservée
    assert eve["status"] == "active" and eve["class_id"] == s.ct["id"] and eve["is_repeater"] is True

    settings = client.get(f"{API}/establishment/settings", headers=s.h).json()
    assert settings["academic_year"] == NEXT and not settings["term_periods"]

    hist = {e["class_name"]: e for e in client.get(f"{API}/students/{s.ada['id']}/enrollments", headers=s.h).json()}
    assert hist["6ème A"]["academic_year"] == YEAR and hist["6ème A"]["outcome"] == "promoted" and hist["6ème A"]["next_class_name"] == "5ème A"
    assert client.get(f"{API}/students/{s.bao['id']}/enrollments", headers=s.h).json()[0]["outcome"] == "repeated"
    assert client.get(f"{API}/students/{s.dan['id']}/enrollments", headers=s.h).json()[0]["outcome"] == "graduated"

    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        logs = db.execute(select(AuditLog).where(AuditLog.action == "academic_year.rolled_over")).scalars().all()
        assert len(logs) == 1
        meta = logs[0].metadata_json
        assert (meta["from_year"], meta["to_year"], meta["promoted"], meta["repeated"], meta["graduated"]) == (YEAR, NEXT, 2, 2, 1)
        assert meta["previous_term_periods"]["T1"]["end"] == "2026-12-15"
        assert len(db.execute(select(StudentEnrollment)).scalars().all()) == 5
    finally:
        db.close()


def test_old_grades_do_not_leak_into_the_new_year_and_stay_readable(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    assert len(client.get(f"{API}/students/{s.ada['id']}/grades", headers=s.h).json()) == 3
    assert _rollover(client, s, _plan(s), dry_run=False).status_code == 200

    assert client.get(f"{API}/students/{s.ada['id']}/grades", headers=s.h).json() == []           # nouvelle année : vierge
    old = client.get(f"{API}/students/{s.ada['id']}/grades", params={"academic_year": YEAR}, headers=s.h).json()
    assert len(old) == 3 and {g["academic_year"] for g in old} == {YEAR}                            # archive consultable

    new = client.post(f"{API}/grades", json={"student_id": s.ada["id"], "subject_id": s.maths["id"], "term": "T1",
                                            "evaluation_label": "D1", "value": 9}, headers=s.h).json()
    assert new["academic_year"] == NEXT
    cur = client.get(f"{API}/students/{s.ada['id']}/grades", params={"term": "T1"}, headers=s.h).json()
    assert [g["value"] for g in cur] == [9.0]                                                      # la moyenne T1 ne mélange pas 15 et 9
    avg = client.get(f"{API}/students/{s.ada['id']}/average", params={"term": "T1"}, headers=s.h).json()
    assert avg["general_average"] == 9.0


def test_grade_of_a_closed_year_is_correctable_only_by_direction_and_traced(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    old = client.get(f"{API}/students/{s.ada['id']}/grades", headers=s.h).json()[0]
    _rollover(client, s, _plan(s), dry_run=False)
    assert client.patch(f"{API}/grades/{old['id']}", json={"value": 18}, headers=s.teacher_h).status_code == 403
    ok = client.patch(f"{API}/grades/{old['id']}", json={"value": 18}, headers=s.h)
    assert ok.status_code == 200 and ok.json()["value"] == 18
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        log = db.execute(select(AuditLog).where(AuditLog.action == "grade.override_closed_year")).scalar_one()
        assert log.metadata_json["academic_year"] == YEAR and log.metadata_json["new_value"] == 18.0
    finally:
        db.close()


# ======================= Refus =======================

def test_second_execution_and_stale_screen_are_refused_with_409(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(s)
    assert _rollover(client, s, plan, dry_run=False).status_code == 200
    again = _rollover(client, s, plan, dry_run=False)
    assert again.status_code == 409 and NEXT in again.json()["detail"]
    assert _get(client, s, s.ada)["class_id"] == s.c5["id"]                                         # pas montée une 2e fois
    assert len(client.get(f"{API}/students/{s.ada['id']}/enrollments", headers=s.h).json()) == 1


def test_a_class_with_active_students_cannot_be_forgotten(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(s, moves=[{"from_class_id": s.c6["id"], "to_class_id": s.c5["id"]}])
    prev = _rollover(client, s, plan).json()
    assert any("5ème A" in e and "Tle A" in e for e in prev["errors"])
    r = _rollover(client, s, plan, dry_run=False)
    assert r.status_code == 422 and "sans destination" in r.json()["detail"]
    assert _get(client, s, s.ada)["class_id"] == s.c6["id"]                                         # tout ou rien
    assert client.get(f"{API}/establishment/settings", headers=s.h).json()["academic_year"] == YEAR


def test_invalid_plans_are_rejected_with_clear_messages(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = _school(client, make_tenant, make_user, auth_headers)

    def errors(plan):
        return _rollover(client, s, plan).json()["errors"]

    assert any("propre destination" in e for e in errors(_plan(s, moves=[
        {"from_class_id": s.c6["id"], "to_class_id": s.c6["id"]},
        {"from_class_id": s.c5["id"], "to_class_id": s.c4["id"]}, {"from_class_id": s.ct["id"], "to_class_id": None}])))
    assert any("n'existe pas" in e for e in errors(_plan(s, moves=[
        {"from_class_id": s.c6["id"], "to_class_id": other.c5["id"]},                                # classe d'un AUTRE établissement
        {"from_class_id": s.c5["id"], "to_class_id": s.c4["id"]}, {"from_class_id": s.ct["id"], "to_class_id": None}])))
    assert any("deux fois" in e for e in errors(_plan(s, moves=[
        {"from_class_id": s.c6["id"], "to_class_id": s.c5["id"]}, {"from_class_id": s.c6["id"], "to_class_id": s.c4["id"]},
        {"from_class_id": s.c5["id"], "to_class_id": s.c4["id"]}, {"from_class_id": s.ct["id"], "to_class_id": None}])))
    assert any("redoublant" in e for e in errors(_plan(s, repeaters=[other.ada])))                   # élève d'un autre établissement
    bad_year = {**_plan(s), "to_year": "2031-2032"}
    assert any("doit être" in e for e in _rollover(client, s, bad_year).json()["errors"])
    assert _rollover(client, s, {**_plan(s), "to_year": "26-27"}).status_code == 422                # format invalide
    skip = _rollover(client, s, bad_year, dry_run=False)                                            # année sautée : refusée aussi à l'exécution
    assert skip.status_code == 422 and _get(client, s, s.ada)["class_id"] == s.c6["id"]


def test_graduated_or_transferred_students_are_left_alone(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post(f"{API}/students/{s.bao['id']}/status", json={"status": "transferred", "reason": "Déménagement"}, headers=s.h)
    rep = _rollover(client, s, _plan(s), dry_run=False).json()
    assert rep["promoted"] == 2  # Ada, Cléo — Bao (transféré) n'est pas promu
    assert _get(client, s, s.bao)["class_id"] == s.c6["id"] and _get(client, s, s.bao)["status"] == "transferred"
    assert client.get(f"{API}/students/{s.bao['id']}/enrollments", headers=s.h).json() == []


def test_roles_only_direction_and_founder_can_close_the_year(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    for role in (UserRole.TEACHER, UserRole.STAFF, UserRole.CENSOR, UserRole.ACCOUNTANT, UserRole.SUPERVISOR):
        u, pwd = make_user(tenant=s.tenant, role=role)
        h = auth_headers(u, pwd)
        assert client.get(f"{API}/academic-year/proposal", headers=h).status_code == 403, role
        assert _rollover(client, s, _plan(s), dry_run=False, headers=h).status_code == 403, role
    assert _get(client, s, s.ada)["class_id"] == s.c6["id"]
    f, pwd = make_user(tenant=s.tenant, role=UserRole.FOUNDER)
    assert _rollover(client, s, _plan(s), headers=auth_headers(f, pwd)).status_code == 200
    # Lecture de l'historique : personnel de l'établissement seulement, jamais un autre établissement.
    other = _school(client, make_tenant, make_user, auth_headers)
    assert client.get(f"{API}/students/{s.ada['id']}/enrollments", headers=other.h).status_code == 404
    assert client.get(f"{API}/students/{s.ada['id']}/enrollments", headers=s.teacher_h).status_code == 200


def test_two_simultaneous_closures_pass_the_year_only_once(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    plan = _plan(s)
    codes: list[int] = []

    def go():
        codes.append(_rollover(client, s, plan, dry_run=False).status_code)

    threads = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [200, 409, 409, 409], codes
    assert _get(client, s, s.ada)["class_id"] == s.c5["id"] and _get(client, s, s.cleo)["class_id"] == s.c4["id"]
    assert len(client.get(f"{API}/students/{s.cleo['id']}/enrollments", headers=s.h).json()) == 1


# ======================= Année « à la main » =======================

def test_year_cannot_be_changed_by_hand_once_grades_exist(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    r = client.patch(f"{API}/establishment/settings", json={"academic_year": next_year(NEXT)}, headers=s.h)
    assert r.status_code == 409 and "Passage d'année" in r.json()["detail"]
    assert client.patch(f"{API}/establishment/settings", json={"academic_year": YEAR}, headers=s.h).status_code == 200  # idem : sans effet
    fresh = make_tenant()
    adm, pwd = make_user(tenant=fresh, role=UserRole.SCHOOL_ADMIN)
    assert client.patch(f"{API}/establishment/settings", json={"academic_year": "2030-2031"}, headers=auth_headers(adm, pwd)).status_code == 200


# ======================= Bulletins et moyennes de classe =======================

def test_new_year_report_cards_and_rankings_ignore_the_closed_year(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    # Année N : Ada (6ème A) a 15 en T1 ; bulletin généré puis publié = figé.
    first = client.post(f"{API}/report-cards/generate", json={"class_id": s.c6["id"], "term": "T1"}, headers=s.h)
    assert first.status_code == 200, first.text
    _rollover(client, s, _plan(s), dry_run=False)
    # Année N+1 : Ada et Bao sont en 5ème A (sans redoublement). Seule Ada reçoit une note T1 : 9.
    client.post(f"{API}/grades", json={"student_id": s.ada["id"], "subject_id": s.maths["id"], "term": "T1",
                                      "evaluation_label": "D1", "value": 9}, headers=s.h)
    assert client.post(f"{API}/report-cards/generate", json={"class_id": s.c5["id"], "term": "T1"}, headers=s.h).status_code == 200
    cards = client.get(f"{API}/report-cards", params={"class_id": s.c5["id"], "term": "T1"}, headers=s.h).json()
    ada = next(c for c in cards if c["student_id"] == s.ada["id"] and c["academic_year"] == NEXT)
    assert ada["general_average"] == 9.0 and ada["rank"] == 1      # 9, et non une moyenne avec les 15 de l'an dernier
    bao = next(c for c in cards if c["student_id"] == s.bao["id"] and c["academic_year"] == NEXT)
    assert bao["general_average"] is None                           # pas de note cette année : pas de reprise de l'ancienne (6)
    # L'archive de l'année close est intacte.
    old = client.get(f"{API}/report-cards", params={"class_id": s.c6["id"], "term": "T1"}, headers=s.h).json()
    assert {c["academic_year"] for c in old} == {YEAR}
