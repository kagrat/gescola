from app.models.user import UserRole


def test_parent_sees_only_linked_child(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd_admin = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers_admin = auth_headers(admin, pwd_admin)

    child_a = client.post("/api/v1/students", json={"first_name": "Enfant", "last_name": "A"}, headers=headers_admin).json()
    child_b = client.post("/api/v1/students", json={"first_name": "Enfant", "last_name": "B"}, headers=headers_admin).json()

    parent_user_resp = client.post(
        "/api/v1/users",
        json={"email": "parent@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent A", "role": "parent"},
        headers=headers_admin,
    ).json()

    link_resp = client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent_user_resp["id"], "student_id": child_a["id"], "relationship_label": "Mère"},
        headers=headers_admin,
    )
    assert link_resp.status_code == 201

    # Connexion du parent avec le mot de passe défini à la création
    login_resp = client.post("/api/v1/auth/login", json={"email": "parent@example.com", "password": "Str0ng#Passw0rd!"})
    assert login_resp.status_code == 200
    parent_token = login_resp.json()["access_token"]
    parent_headers = {"Authorization": f"Bearer {parent_token}"}

    children_resp = client.get("/api/v1/me/children", headers=parent_headers)
    assert children_resp.status_code == 200
    ids = {c["id"] for c in children_resp.json()}
    assert ids == {child_a["id"]}
    assert child_b["id"] not in ids

    # Accès direct à son propre enfant : OK
    grades_a = client.get(f"/api/v1/children/{child_a['id']}/grades", headers=parent_headers)
    assert grades_a.status_code == 200

    # Accès direct à un autre enfant (même établissement, non rattaché) : 404, jamais 403
    grades_b = client.get(f"/api/v1/children/{child_b['id']}/grades", headers=parent_headers)
    assert grades_b.status_code == 404


def test_parent_cannot_access_general_student_endpoints(client, make_tenant, make_user, auth_headers):
    """Le rôle PARENT n'a jamais accès aux endpoints du personnel, même pour
    son propre enfant — seuls les endpoints /me/children et /children/{id}/*
    lui sont ouverts."""
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers_admin = auth_headers(admin, pwd)

    parent_resp = client.post(
        "/api/v1/users",
        json={"email": "parent2@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers_admin,
    ).json()
    login_resp = client.post("/api/v1/auth/login", json={"email": "parent2@example.com", "password": "Str0ng#Passw0rd!"})
    parent_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = client.get("/api/v1/students", headers=parent_headers)
    assert resp.status_code == 403


def test_parent_can_view_average_attendance_and_invoices_of_linked_child(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers_admin = auth_headers(admin, pwd)

    child = client.post("/api/v1/students", json={"first_name": "Enfant", "last_name": "C"}, headers=headers_admin).json()
    subject = client.post("/api/v1/subjects", json={"name": "Anglais"}, headers=headers_admin).json()
    client.post(
        "/api/v1/grades",
        json={"student_id": child["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 15},
        headers=headers_admin,
    )
    client.post("/api/v1/attendance", json={"student_id": child["id"], "date": "2026-10-05", "status": "present"}, headers=headers_admin)
    client.post(
        "/api/v1/invoices",
        json={"student_id": child["id"], "label": "Scolarité", "amount_due": 20000, "due_date": "2026-10-01"},
        headers=headers_admin,
    )

    parent = client.post(
        "/api/v1/users",
        json={"email": "parent-full@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers_admin,
    ).json()
    client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent["id"], "student_id": child["id"], "relationship_label": "Mère"},
        headers=headers_admin,
    )
    login_resp = client.post("/api/v1/auth/login", json={"email": "parent-full@example.com", "password": "Str0ng#Passw0rd!"})
    parent_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    avg_resp = client.get(f"/api/v1/children/{child['id']}/average", params={"term": "T1"}, headers=parent_headers)
    assert avg_resp.status_code == 200
    assert avg_resp.json()["general_average"] == 15.0

    attendance_resp = client.get(f"/api/v1/children/{child['id']}/attendance", headers=parent_headers)
    assert attendance_resp.status_code == 200
    assert len(attendance_resp.json()) == 1

    invoices_resp = client.get(f"/api/v1/children/{child['id']}/invoices", headers=parent_headers)
    assert invoices_resp.status_code == 200
    assert invoices_resp.json()[0]["amount_due"] == 20000.0

    # Autre parent, non rattaché : aucun de ces trois endpoints ne doit répondre 200
    other_parent = client.post(
        "/api/v1/users",
        json={"email": "other-parent@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Autre", "role": "parent"},
        headers=headers_admin,
    ).json()
    other_login = client.post("/api/v1/auth/login", json={"email": "other-parent@example.com", "password": "Str0ng#Passw0rd!"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    assert client.get(f"/api/v1/children/{child['id']}/average", params={"term": "T1"}, headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/children/{child['id']}/attendance", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/children/{child['id']}/invoices", headers=other_headers).status_code == 404


def test_only_admin_or_staff_can_create_guardian_link(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    teacher, pwd = make_user(tenant=tenant, role=UserRole.TEACHER)
    admin, pwd_admin = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers_admin = auth_headers(admin, pwd_admin)

    student = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y"}, headers=headers_admin).json()
    parent = client.post(
        "/api/v1/users",
        json={"email": "p3@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers_admin,
    ).json()

    resp = client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent["id"], "student_id": student["id"], "relationship_label": "Père"},
        headers=auth_headers(teacher, pwd),
    )
    assert resp.status_code == 403


def test_guardian_link_rejects_non_parent_role(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y"}, headers=headers).json()
    teacher = client.post(
        "/api/v1/users",
        json={"email": "notparent@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Prof", "role": "teacher"},
        headers=headers,
    ).json()

    resp = client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": teacher["id"], "student_id": student["id"], "relationship_label": "Père"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_guardian_link_to_student_of_another_tenant_returns_404(client, make_tenant, make_user, auth_headers):
    tenant_a = make_tenant()
    tenant_b = make_tenant()
    admin_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.SCHOOL_ADMIN)
    admin_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SCHOOL_ADMIN)

    student_b = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y"}, headers=auth_headers(admin_b, pwd_b)).json()
    parent_a = client.post(
        "/api/v1/users",
        json={"email": "parent-a@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent A", "role": "parent"},
        headers=auth_headers(admin_a, pwd_a),
    ).json()

    resp = client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent_a["id"], "student_id": student_b["id"], "relationship_label": "Père"},
        headers=auth_headers(admin_a, pwd_a),
    )
    assert resp.status_code == 404


def test_duplicate_guardian_link_rejected(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y"}, headers=headers).json()
    parent = client.post(
        "/api/v1/users",
        json={"email": "dup-parent@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers,
    ).json()
    payload = {"parent_user_id": parent["id"], "student_id": student["id"], "relationship_label": "Mère"}
    first = client.post("/api/v1/guardian-links", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/guardian-links", json=payload, headers=headers)
    assert second.status_code == 409


def test_list_and_delete_guardian_link(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y"}, headers=headers).json()
    parent = client.post(
        "/api/v1/users",
        json={"email": "list-parent@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers,
    ).json()
    link = client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent["id"], "student_id": student["id"], "relationship_label": "Mère"},
        headers=headers,
    ).json()

    listed = client.get("/api/v1/guardian-links", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == link["id"]

    delete_resp = client.delete(f"/api/v1/guardian-links/{link['id']}", headers=headers)
    assert delete_resp.status_code == 204

    listed_after = client.get("/api/v1/guardian-links", headers=headers).json()
    assert listed_after == []

    # Le parent perd effectivement l'accès une fois le rattachement retiré
    login_resp = client.post("/api/v1/auth/login", json={"email": "list-parent@example.com", "password": "Str0ng#Passw0rd!"})
    parent_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    children = client.get("/api/v1/me/children", headers=parent_headers)
    assert children.json() == []


def test_teacher_cannot_list_or_delete_guardian_links(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    teacher, pwd = make_user(tenant=tenant, role=UserRole.TEACHER)
    headers = auth_headers(teacher, pwd)
    assert client.get("/api/v1/guardian-links", headers=headers).status_code == 403
    assert client.delete("/api/v1/guardian-links/00000000-0000-0000-0000-000000000000", headers=headers).status_code == 403
