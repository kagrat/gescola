from app.models.user import UserRole

INCIDENT = {
    "occurred_at": "2026-10-05T09:15:00+00:00",
    "category": "behavior",
    "severity": "moderate",
    "description": "Comportement perturbateur pendant la récréation.",
}


def _setup(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    admin_headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "Jean", "last_name": "Koffi"}, headers=admin_headers).json()
    return tenant, admin_headers, student


def test_supervisor_reports_and_censor_sees_it(client, make_tenant, make_user, auth_headers):
    tenant, _admin_headers, student = _setup(client, make_tenant, make_user, auth_headers)
    supervisor, pwd_s = make_user(tenant=tenant, role=UserRole.SUPERVISOR)
    censor, pwd_c = make_user(tenant=tenant, role=UserRole.CENSOR)

    resp = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=auth_headers(supervisor, pwd_s))
    assert resp.status_code == 201
    assert resp.json()["status"] == "reported"
    assert resp.json()["sanctions"] == []

    listed = client.get("/api/v1/incidents", headers=auth_headers(censor, pwd_c))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_teacher_only_sees_own_reports(client, make_tenant, make_user, auth_headers):
    tenant, _h, student = _setup(client, make_tenant, make_user, auth_headers)
    teacher_a, pwd_a = make_user(tenant=tenant, role=UserRole.TEACHER)
    teacher_b, pwd_b = make_user(tenant=tenant, role=UserRole.TEACHER)

    client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=auth_headers(teacher_a, pwd_a))

    assert len(client.get("/api/v1/incidents", headers=auth_headers(teacher_a, pwd_a)).json()) == 1
    assert client.get("/api/v1/incidents", headers=auth_headers(teacher_b, pwd_b)).json() == []


def test_reporters_cannot_sanction_or_change_status(client, make_tenant, make_user, auth_headers):
    tenant, _h, student = _setup(client, make_tenant, make_user, auth_headers)
    supervisor, pwd_s = make_user(tenant=tenant, role=UserRole.SUPERVISOR)
    teacher, pwd_t = make_user(tenant=tenant, role=UserRole.TEACHER)
    incident = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=auth_headers(supervisor, pwd_s)).json()

    for user, pwd in [(supervisor, pwd_s), (teacher, pwd_t)]:
        headers = auth_headers(user, pwd)
        assert client.post(f"/api/v1/incidents/{incident['id']}/sanctions", json={"sanction_type": "warning"}, headers=headers).status_code == 403
        assert client.patch(f"/api/v1/incidents/{incident['id']}/status", json={"status": "resolved"}, headers=headers).status_code == 403


def test_censor_imposes_sanction_and_resolves(client, make_tenant, make_user, auth_headers):
    tenant, _h, student = _setup(client, make_tenant, make_user, auth_headers)
    supervisor, pwd_s = make_user(tenant=tenant, role=UserRole.SUPERVISOR)
    censor, pwd_c = make_user(tenant=tenant, role=UserRole.CENSOR)
    incident = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=auth_headers(supervisor, pwd_s)).json()
    censor_headers = auth_headers(censor, pwd_c)

    review = client.patch(f"/api/v1/incidents/{incident['id']}/status", json={"status": "under_review"}, headers=censor_headers)
    assert review.status_code == 200 and review.json()["status"] == "under_review"

    sanction = client.post(
        f"/api/v1/incidents/{incident['id']}/sanctions",
        json={"sanction_type": "detention", "details": "2 heures samedi", "start_date": "2026-10-10", "end_date": "2026-10-10"},
        headers=censor_headers,
    )
    assert sanction.status_code == 201
    assert len(sanction.json()["sanctions"]) == 1
    assert sanction.json()["sanctions"][0]["sanction_type"] == "detention"

    resolved = client.patch(f"/api/v1/incidents/{incident['id']}/status", json={"status": "resolved"}, headers=censor_headers)
    assert resolved.json()["status"] == "resolved"


def test_sanction_end_date_before_start_rejected(client, make_tenant, make_user, auth_headers):
    tenant, admin_headers, student = _setup(client, make_tenant, make_user, auth_headers)
    incident = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=admin_headers).json()
    resp = client.post(
        f"/api/v1/incidents/{incident['id']}/sanctions",
        json={"sanction_type": "detention", "start_date": "2026-10-10", "end_date": "2026-10-01"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_founder_and_school_admin_can_manage(client, make_tenant, make_user, auth_headers):
    tenant, admin_headers, student = _setup(client, make_tenant, make_user, auth_headers)
    founder, pwd_f = make_user(tenant=tenant, role=UserRole.FOUNDER)
    incident = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=admin_headers).json()
    assert client.post(f"/api/v1/incidents/{incident['id']}/sanctions", json={"sanction_type": "warning"}, headers=auth_headers(founder, pwd_f)).status_code == 201


def test_other_roles_have_no_access(client, make_tenant, make_user, auth_headers):
    tenant, _h, student = _setup(client, make_tenant, make_user, auth_headers)
    for role in (UserRole.ACCOUNTANT, UserRole.STAFF, UserRole.PARENT):
        user, pwd = make_user(tenant=tenant, role=role)
        headers = auth_headers(user, pwd)
        assert client.get("/api/v1/incidents", headers=headers).status_code == 403
        assert client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=headers).status_code == 403


def test_cannot_report_incident_for_student_of_another_tenant(client, make_tenant, make_user, auth_headers):
    _tenant_a, _h, student_a = _setup(client, make_tenant, make_user, auth_headers)
    tenant_b = make_tenant()
    supervisor_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SUPERVISOR)
    resp = client.post("/api/v1/incidents", json={"student_id": student_a["id"], **INCIDENT}, headers=auth_headers(supervisor_b, pwd_b))
    assert resp.status_code == 404


def test_incidents_isolated_between_tenants(client, make_tenant, make_user, auth_headers):
    tenant_a, admin_headers_a, student_a = _setup(client, make_tenant, make_user, auth_headers)
    client.post("/api/v1/incidents", json={"student_id": student_a["id"], **INCIDENT}, headers=admin_headers_a)
    tenant_b = make_tenant()
    admin_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SCHOOL_ADMIN)
    assert client.get("/api/v1/incidents", headers=auth_headers(admin_b, pwd_b)).json() == []


def test_filter_by_student_and_status_and_audit_trail(client, make_tenant, make_user, auth_headers):
    tenant, admin_headers, student = _setup(client, make_tenant, make_user, auth_headers)
    other = client.post("/api/v1/students", json={"first_name": "Paul", "last_name": "André"}, headers=admin_headers).json()
    first = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT}, headers=admin_headers).json()
    client.post("/api/v1/incidents", json={"student_id": other["id"], **INCIDENT}, headers=admin_headers)
    client.patch(f"/api/v1/incidents/{first['id']}/status", json={"status": "resolved"}, headers=admin_headers)

    assert len(client.get(f"/api/v1/incidents?student_id={student['id']}", headers=admin_headers).json()) == 1
    assert len(client.get("/api/v1/incidents?status=resolved", headers=admin_headers).json()) == 1
    assert len(client.get("/api/v1/incidents?status=reported", headers=admin_headers).json()) == 1

    actions = {log["action"] for log in client.get("/api/v1/audit-logs", headers=admin_headers).json()}
    assert {"incident.reported", "incident.status_changed"} <= actions


def test_blank_description_rejected(client, make_tenant, make_user, auth_headers):
    tenant, admin_headers, student = _setup(client, make_tenant, make_user, auth_headers)
    resp = client.post("/api/v1/incidents", json={"student_id": student["id"], **INCIDENT, "description": "   "}, headers=admin_headers)
    assert resp.status_code == 422
