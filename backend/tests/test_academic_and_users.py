from app.models.user import UserRole


def test_attendance_create_and_list(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    staff, pwd = make_user(tenant=tenant, role=UserRole.STAFF)
    headers = auth_headers(staff, pwd)

    student = client.post("/api/v1/students", json={"first_name": "Chabi", "last_name": "Orou"}, headers=headers).json()

    resp = client.post(
        "/api/v1/attendance",
        json={"student_id": student["id"], "date": "2026-10-05", "status": "absent", "justified": False},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "absent"

    listed = client.get(f"/api/v1/students/{student['id']}/attendance", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_attendance_for_unknown_student_returns_404(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    staff, pwd = make_user(tenant=tenant, role=UserRole.STAFF)
    headers = auth_headers(staff, pwd)
    resp = client.post(
        "/api/v1/attendance",
        json={"student_id": "00000000-0000-0000-0000-000000000000", "date": "2026-10-05", "status": "present"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_school_admin_creates_and_lists_users(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    create_resp = client.post(
        "/api/v1/users",
        json={"email": "prof.diallo@example.com", "password": "Str0ng#Passw0rd!", "full_name": "M. Diallo", "role": "teacher"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["role"] == "teacher"

    list_resp = client.get("/api/v1/users", headers=headers)
    assert list_resp.status_code == 200
    emails = {u["email"] for u in list_resp.json()}
    assert "prof.diallo@example.com" in emails
    assert admin.email in emails  # l'admin lui-même apparaît dans son propre établissement


def test_duplicate_email_within_same_tenant_rejected(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    payload = {"email": "double@example.com", "password": "Str0ng#Passw0rd!", "full_name": "X", "role": "teacher"}
    first = client.post("/api/v1/users", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/users", json=payload, headers=headers)
    assert second.status_code == 409


def test_super_admin_cannot_be_attached_to_tenant(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    resp = client.post(
        "/api/v1/users",
        json={"email": "x@example.com", "password": "Str0ng#Passw0rd!", "full_name": "X", "role": "super_admin"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_classes_and_subjects_crud(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    staff, pwd = make_user(tenant=tenant, role=UserRole.STAFF)
    headers = auth_headers(staff, pwd)

    class_resp = client.post("/api/v1/classes", json={"name": "CM2 A", "level": "CM2"}, headers=headers)
    assert class_resp.status_code == 201
    classes = client.get("/api/v1/classes", headers=headers).json()
    assert len(classes) == 1

    subject_resp = client.post("/api/v1/subjects", json={"name": "Histoire-Géo", "default_coefficient": 2}, headers=headers)
    assert subject_resp.status_code == 201
    subjects = client.get("/api/v1/subjects", headers=headers).json()
    assert len(subjects) == 1


def test_student_cannot_be_attached_to_class_of_another_tenant(client, make_tenant, make_user, auth_headers):
    tenant_a = make_tenant()
    tenant_b = make_tenant()
    staff_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.STAFF)
    staff_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.STAFF)

    class_b = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème"}, headers=auth_headers(staff_b, pwd_b)).json()

    resp = client.post(
        "/api/v1/students",
        json={"first_name": "X", "last_name": "Y", "class_id": class_b["id"]},
        headers=auth_headers(staff_a, pwd_a),
    )
    assert resp.status_code == 404
