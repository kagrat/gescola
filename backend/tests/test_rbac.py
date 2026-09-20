from app.models.user import UserRole


def test_teacher_cannot_create_student(client, make_user, auth_headers):
    teacher, pwd = make_user(role=UserRole.TEACHER)
    headers = auth_headers(teacher, pwd)
    resp = client.post("/api/v1/students", json={"first_name": "Test", "last_name": "Eleve"}, headers=headers)
    assert resp.status_code == 403


def test_staff_can_create_student(client, make_user, auth_headers):
    staff, pwd = make_user(role=UserRole.STAFF)
    headers = auth_headers(staff, pwd)
    resp = client.post("/api/v1/students", json={"first_name": "Test", "last_name": "Eleve"}, headers=headers)
    assert resp.status_code == 201


def test_teacher_can_create_grade_but_not_lock_it(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd_admin = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    teacher, pwd_teacher = make_user(tenant=tenant, role=UserRole.TEACHER)

    headers_admin = auth_headers(admin, pwd_admin)
    headers_teacher = auth_headers(teacher, pwd_teacher)

    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers_admin).json()
    subject = client.post("/api/v1/subjects", json={"name": "Français"}, headers=headers_admin).json()

    grade_resp = client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 12},
        headers=headers_teacher,
    )
    assert grade_resp.status_code == 201

    # Un enseignant ne peut pas verrouiller les notes (réservé à la direction)
    lock_resp = client.post(
        f"/api/v1/students/{student['id']}/grades/lock", params={"term": "T1"}, headers=headers_teacher
    )
    assert lock_resp.status_code == 403

    lock_resp_admin = client.post(
        f"/api/v1/students/{student['id']}/grades/lock", params={"term": "T1"}, headers=headers_admin
    )
    assert lock_resp_admin.status_code == 200
    assert lock_resp_admin.json()["locked_count"] == 1


def test_only_super_admin_can_create_tenant(client, make_user, auth_headers):
    school_admin, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    resp = client.post(
        "/api/v1/tenants", json={"name": "Nouvelle École", "code": "new-school"}, headers=auth_headers(school_admin, pwd)
    )
    assert resp.status_code == 403

    super_admin, pwd2 = make_user(role=UserRole.SUPER_ADMIN)
    resp2 = client.post(
        "/api/v1/tenants", json={"name": "Nouvelle École", "code": "new-school"}, headers=auth_headers(super_admin, pwd2)
    )
    assert resp2.status_code == 201


def test_weak_password_rejected_on_user_creation(client, make_user, auth_headers):
    admin, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    resp = client.post(
        "/api/v1/users",
        json={"email": "faible@example.com", "password": "123456", "full_name": "Test", "role": "teacher"},
        headers=headers,
    )
    assert resp.status_code == 422
