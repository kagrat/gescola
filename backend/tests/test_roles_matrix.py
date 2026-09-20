from app.models.user import UserRole


def _bootstrap(make_tenant, make_user, auth_headers, client):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers_admin = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "Séna", "last_name": "Agossou"}, headers=headers_admin).json()
    subject = client.post("/api/v1/subjects", json={"name": "Physique"}, headers=headers_admin).json()
    return tenant, headers_admin, student, subject


def test_censor_can_lock_grades_but_not_manage_users_or_finance(client, make_tenant, make_user, auth_headers):
    tenant, headers_admin, student, subject = _bootstrap(make_tenant, make_user, auth_headers, client)
    censor, pwd = make_user(tenant=tenant, role=UserRole.CENSOR)
    headers_censor = auth_headers(censor, pwd)

    client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 14},
        headers=headers_admin,
    )

    # Le censeur peut consulter les notes et verrouiller la période (validation des bulletins)
    read_resp = client.get(f"/api/v1/students/{student['id']}/grades", params={"term": "T1"}, headers=headers_censor)
    assert read_resp.status_code == 200

    lock_resp = client.post(f"/api/v1/students/{student['id']}/grades/lock", params={"term": "T1"}, headers=headers_censor)
    assert lock_resp.status_code == 200
    assert lock_resp.json()["locked_count"] == 1

    # Mais ni la gestion des comptes...
    create_user_resp = client.post(
        "/api/v1/users",
        json={"email": "x@example.com", "password": "Str0ng#Passw0rd!", "full_name": "X", "role": "teacher"},
        headers=headers_censor,
    )
    assert create_user_resp.status_code == 403

    # ...ni les finances
    invoice_resp = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 5000, "due_date": "2026-10-01"},
        headers=headers_censor,
    )
    assert invoice_resp.status_code == 403


def test_supervisor_can_record_attendance_but_not_grades(client, make_tenant, make_user, auth_headers):
    tenant, headers_admin, student, subject = _bootstrap(make_tenant, make_user, auth_headers, client)
    supervisor, pwd = make_user(tenant=tenant, role=UserRole.SUPERVISOR)
    headers_supervisor = auth_headers(supervisor, pwd)

    attendance_resp = client.post(
        "/api/v1/attendance",
        json={"student_id": student["id"], "date": "2026-10-05", "status": "absent"},
        headers=headers_supervisor,
    )
    assert attendance_resp.status_code == 201

    grade_resp = client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 10},
        headers=headers_supervisor,
    )
    assert grade_resp.status_code == 403

    # Le surveillant n'a pas non plus accès en lecture aux notes (rôle disciplinaire, pas pédagogique)
    read_resp = client.get(f"/api/v1/students/{student['id']}/grades", headers=headers_supervisor)
    assert read_resp.status_code == 403


def test_accountant_can_manage_finance_but_not_write_registry(client, make_tenant, make_user, auth_headers):
    tenant, headers_admin, student, _subject = _bootstrap(make_tenant, make_user, auth_headers, client)
    accountant, pwd = make_user(tenant=tenant, role=UserRole.ACCOUNTANT)
    headers_accountant = auth_headers(accountant, pwd)

    invoice_resp = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité T1", "amount_due": 75000, "due_date": "2026-10-01"},
        headers=headers_accountant,
    )
    assert invoice_resp.status_code == 201

    student_create_resp = client.post(
        "/api/v1/students", json={"first_name": "Autre", "last_name": "Eleve"}, headers=headers_accountant
    )
    assert student_create_resp.status_code == 403


def test_school_admin_can_create_every_internal_role(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    for role in ["censor", "supervisor", "accountant", "staff", "teacher", "parent"]:
        resp = client.post(
            "/api/v1/users",
            json={"email": f"{role}@example.com", "password": "Str0ng#Passw0rd!", "full_name": role, "role": role},
            headers=headers,
        )
        assert resp.status_code == 201, f"échec pour le rôle {role}: {resp.text}"

    # Le Super Admin ne peut jamais être créé depuis un établissement
    resp = client.post(
        "/api/v1/users",
        json={"email": "super@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Super", "role": "super_admin"},
        headers=headers,
    )
    assert resp.status_code == 400
