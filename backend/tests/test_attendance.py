import json
import uuid

from app.models.user import UserRole


class School:
    """Établissement de test : une classe de deux élèves, un enseignant affecté à
    cette classe, un autre sans aucune affectation (grandfathering)."""


def _school(client, make_tenant, make_user, auth_headers):
    s = School()
    s.tenant = make_tenant()
    s.admin, pwd = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN, full_name="Mme Direction")
    s.admin_h = auth_headers(s.admin, pwd)
    s.teacher_a, pwd_a = make_user(tenant=s.tenant, role=UserRole.TEACHER, full_name="M. Prof A")
    s.teacher_a_h = auth_headers(s.teacher_a, pwd_a)
    s.teacher_none, pwd_n = make_user(tenant=s.tenant, role=UserRole.TEACHER, full_name="M. Prof Sans Classe")
    s.teacher_none_h = auth_headers(s.teacher_none, pwd_n)
    s.cls = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème"}, headers=s.admin_h).json()
    s.other_cls = client.post("/api/v1/classes", json={"name": "5ème B", "level": "5ème"}, headers=s.admin_h).json()
    subject = client.post("/api/v1/subjects", json={"name": "Mathématiques"}, headers=s.admin_h).json()
    r = client.post("/api/v1/teacher-assignments", json={"teacher_id": str(s.teacher_a.id), "class_id": s.cls["id"], "subject_id": subject["id"]}, headers=s.admin_h)
    assert r.status_code == 201
    # teacher_none a une affectation, mais ailleurs (5ème B) : "configuré", donc bien restreint hors de sa classe —
    # à distinguer d'un enseignant sans aucune affectation nulle part, qui lui n'est jamais restreint (grandfathering).
    r2 = client.post("/api/v1/teacher-assignments", json={"teacher_id": str(s.teacher_none.id), "class_id": s.other_cls["id"], "subject_id": subject["id"]}, headers=s.admin_h)
    assert r2.status_code == 201
    s.kid1 = client.post("/api/v1/students", json={"first_name": "Aya", "last_name": "Diallo", "class_id": s.cls["id"]}, headers=s.admin_h).json()
    s.kid2 = client.post("/api/v1/students", json={"first_name": "Koffi", "last_name": "Mensah", "class_id": s.cls["id"]}, headers=s.admin_h).json()
    s.other_kid = client.post("/api/v1/students", json={"first_name": "Zoé", "last_name": "Autre", "class_id": s.other_cls["id"]}, headers=s.admin_h).json()
    return s


def _roster(client, headers, class_id, date="2026-10-05"):
    return client.get(f"/api/v1/classes/{class_id}/attendance", params={"date": date}, headers=headers)


# ======================= Appel en masse =======================

def test_bulk_roll_call_creates_records_for_the_whole_class(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    empty_roster = _roster(client, s.admin_h, s.cls["id"]).json()
    assert len(empty_roster) == 2 and all(r["status"] is None for r in empty_roster)

    resp = client.post("/api/v1/attendance/bulk", json={
        "class_id": s.cls["id"], "date": "2026-10-05",
        "entries": [
            {"student_id": s.kid1["id"], "status": "present"},
            {"student_id": s.kid2["id"], "status": "absent", "justified": False},
        ],
    }, headers=s.teacher_a_h)
    assert resp.status_code == 201 and len(resp.json()) == 2

    roster = {r["student_id"]: r for r in _roster(client, s.admin_h, s.cls["id"]).json()}
    assert roster[s.kid1["id"]]["status"] == "present"
    assert roster[s.kid2["id"]]["status"] == "absent" and roster[s.kid2["id"]]["justified"] is False
    assert roster[s.kid1["id"]]["attendance_id"] is not None


def test_bulk_roll_call_the_same_day_corrects_instead_of_duplicating(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    body = {"class_id": s.cls["id"], "date": "2026-10-05", "entries": [{"student_id": s.kid1["id"], "status": "absent"}, {"student_id": s.kid2["id"], "status": "present"}]}
    client.post("/api/v1/attendance/bulk", json=body, headers=s.admin_h)
    same_day_corrected = {**body, "entries": [{"student_id": s.kid1["id"], "status": "present"}, {"student_id": s.kid2["id"], "status": "late"}]}
    resp = client.post("/api/v1/attendance/bulk", json=same_day_corrected, headers=s.admin_h)
    assert resp.status_code == 201

    roster = {r["student_id"]: r for r in _roster(client, s.admin_h, s.cls["id"]).json()}
    assert roster[s.kid1["id"]]["status"] == "present" and roster[s.kid2["id"]]["status"] == "late"
    listed = client.get(f"/api/v1/students/{s.kid1['id']}/attendance", headers=s.admin_h).json()
    assert len(listed) == 1, "un seul enregistrement pour ce jour, pas un doublon"


def test_bulk_roll_call_rejects_students_outside_the_class(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    resp = client.post("/api/v1/attendance/bulk", json={
        "class_id": s.cls["id"], "date": "2026-10-05",
        "entries": [{"student_id": s.kid1["id"], "status": "present"}, {"student_id": s.other_kid["id"], "status": "present"}],
    }, headers=s.admin_h)
    assert resp.status_code == 400


def test_bulk_roll_call_validation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    base = {"class_id": s.cls["id"], "date": "2026-10-05"}
    assert client.post("/api/v1/attendance/bulk", json={**base, "entries": []}, headers=s.admin_h).status_code == 422
    dup = [{"student_id": s.kid1["id"], "status": "present"}, {"student_id": s.kid1["id"], "status": "absent"}]
    assert client.post("/api/v1/attendance/bulk", json={**base, "entries": dup}, headers=s.admin_h).status_code == 422
    unknown_class = client.post("/api/v1/attendance/bulk", json={"class_id": "00000000-0000-0000-0000-000000000000", "date": "2026-10-05", "entries": [{"student_id": s.kid1["id"], "status": "present"}]}, headers=s.admin_h)
    assert unknown_class.status_code == 404


def test_bulk_roll_call_respects_teacher_class_restriction(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    body = {"class_id": s.cls["id"], "date": "2026-10-05", "entries": [{"student_id": s.kid1["id"], "status": "present"}]}
    assert client.post("/api/v1/attendance/bulk", json=body, headers=s.teacher_a_h).status_code == 201            # affecté à cette classe
    assert client.post("/api/v1/attendance/bulk", json=body, headers=s.teacher_none_h).status_code == 403         # aucune affectation ici

    # Professeur principal sans affectation de matière : autorisé quand même.
    client.patch(f"/api/v1/classes/{s.other_cls['id']}", json={"head_teacher_id": str(s.teacher_none.id)}, headers=s.admin_h)
    other_body = {"class_id": s.other_cls["id"], "date": "2026-10-05", "entries": [{"student_id": s.other_kid["id"], "status": "present"}]}
    assert client.post("/api/v1/attendance/bulk", json=other_body, headers=s.teacher_none_h).status_code == 201


def test_roster_and_bulk_isolated_between_schools(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    other = make_tenant()
    foreign_admin, p = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    foreign_h = auth_headers(foreign_admin, p)
    assert _roster(client, foreign_h, s.cls["id"]).status_code == 404
    body = {"class_id": s.cls["id"], "date": "2026-10-05", "entries": [{"student_id": s.kid1["id"], "status": "present"}]}
    assert client.post("/api/v1/attendance/bulk", json=body, headers=foreign_h).status_code == 404


# ======================= Correction après coup =======================

def test_correcting_a_record_is_audited_with_old_and_new_status(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    created = client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "absent"}, headers=s.admin_h).json()

    fixed = client.patch(f"/api/v1/attendance/{created['id']}", json={"status": "present"}, headers=s.admin_h)
    assert fixed.status_code == 200 and fixed.json()["status"] == "present"

    logs = client.get("/api/v1/audit-logs", headers=s.admin_h).json()
    entry = next(l for l in logs if l["action"] == "attendance.corrected")
    assert entry["metadata_json"]["from"] == "absent" and entry["metadata_json"]["to"] == "present"


def test_justifying_an_absence_without_changing_status_is_not_audited(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    created = client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "absent", "justified": False}, headers=s.admin_h).json()
    resp = client.patch(f"/api/v1/attendance/{created['id']}", json={"justified": True}, headers=s.admin_h)
    assert resp.status_code == 200 and resp.json()["justified"] is True and resp.json()["status"] == "absent"
    actions = [l["action"] for l in client.get("/api/v1/audit-logs", headers=s.admin_h).json()]
    assert "attendance.corrected" not in actions


def test_update_respects_teacher_restriction_and_isolation(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    created = client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "absent"}, headers=s.admin_h).json()
    assert client.patch(f"/api/v1/attendance/{created['id']}", json={"status": "present"}, headers=s.teacher_none_h).status_code == 403
    assert client.patch(f"/api/v1/attendance/{created['id']}", json={"status": "present"}, headers=s.teacher_a_h).status_code == 200

    other = make_tenant()
    foreign_admin, p = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    assert client.patch(f"/api/v1/attendance/{created['id']}", json={"status": "late"}, headers=auth_headers(foreign_admin, p)).status_code == 404


def test_update_unknown_record_returns_404(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    resp = client.patch("/api/v1/attendance/00000000-0000-0000-0000-000000000000", json={"status": "present"}, headers=s.admin_h)
    assert resp.status_code == 404


# ======================= Doublon impossible (contrainte) =======================

def test_single_post_upserts_instead_of_duplicating(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    first = client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "absent"}, headers=s.admin_h)
    second = client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "present"}, headers=s.admin_h)
    assert first.status_code == 201 and second.status_code == 201
    listed = client.get(f"/api/v1/students/{s.kid1['id']}/attendance", headers=s.admin_h).json()
    assert len(listed) == 1 and listed[0]["status"] == "present"


def test_single_post_respects_teacher_class_restriction(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    body = {"student_id": s.kid1["id"], "date": "2026-10-05", "status": "present"}
    assert client.post("/api/v1/attendance", json=body, headers=s.teacher_none_h).status_code == 403
    assert client.post("/api/v1/attendance", json=body, headers=s.teacher_a_h).status_code == 201


def test_single_post_for_student_without_class_denies_restricted_teacher_but_allows_others(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    orphan = client.post("/api/v1/students", json={"first_name": "Sans", "last_name": "Classe"}, headers=s.admin_h).json()
    body = {"student_id": orphan["id"], "date": "2026-10-05", "status": "present"}
    assert client.post("/api/v1/attendance", json=body, headers=s.teacher_a_h).status_code == 403     # affecté ailleurs, restreint
    assert client.post("/api/v1/attendance", json=body, headers=s.admin_h).status_code == 201


# ======================= Registre (roster) =======================

def test_roster_reflects_prior_bulk_entries_and_defaults_to_null(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-06", "status": "late", "justified": True}, headers=s.admin_h)
    roster = {r["student_id"]: r for r in _roster(client, s.admin_h, s.cls["id"], date="2026-10-06").json()}
    assert roster[s.kid1["id"]]["status"] == "late" and roster[s.kid1["id"]]["justified"] is True
    assert roster[s.kid2["id"]]["status"] is None and roster[s.kid2["id"]]["attendance_id"] is None
    # élève d'une classe différente : absent du registre
    assert s.other_kid["id"] not in roster


def test_roster_only_lists_active_students(client, make_tenant, make_user, auth_headers, tenant_db_session):
    # Aucun endpoint ne permet de changer le statut d'un élève (ROADMAP AU-23) : on le
    # fait directement en base, comme le reste de la suite le fait déjà pour ce cas.
    s = _school(client, make_tenant, make_user, auth_headers)
    from app.models.student import Student, StudentStatus
    db = tenant_db_session(s.tenant.id)
    try:
        student = db.get(Student, uuid.UUID(s.kid2["id"]))
        student.status = StudentStatus.TRANSFERRED
        db.commit()
    finally:
        db.close()
    roster = _roster(client, s.admin_h, s.cls["id"]).json()
    assert {r["student_id"] for r in roster} == {s.kid1["id"]}


# ======================= Rôles =======================

def test_other_roles_use_attendance_as_before(client, make_tenant, make_user, auth_headers):
    s = _school(client, make_tenant, make_user, auth_headers)
    for role in (UserRole.CENSOR, UserRole.SUPERVISOR, UserRole.STAFF, UserRole.FOUNDER):
        user, pwd = make_user(tenant=s.tenant, role=role)
        headers = auth_headers(user, pwd)
        assert client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "present"}, headers=headers).status_code == 201
    for role in (UserRole.ACCOUNTANT, UserRole.PARENT):
        user, pwd = make_user(tenant=s.tenant, role=role)
        assert client.post("/api/v1/attendance", json={"student_id": s.kid1["id"], "date": "2026-10-05", "status": "present"}, headers=auth_headers(user, pwd)).status_code == 403
