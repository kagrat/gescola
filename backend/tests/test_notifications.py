from app.models.user import UserRole


def test_invoice_reminder_notifies_linked_guardian(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    student = client.post("/api/v1/students", json={"first_name": "Fifamè", "last_name": "Zinsou"}, headers=headers).json()
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité T1", "amount_due": 50000, "due_date": "2026-10-01"},
        headers=headers,
    ).json()

    parent = client.post(
        "/api/v1/users",
        json={"email": "parent-reminder@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent["id"], "student_id": student["id"], "relationship_label": "Mère"},
        headers=headers,
    )

    remind_resp = client.post(f"/api/v1/invoices/{invoice['id']}/remind", headers=headers)
    assert remind_resp.status_code == 200
    assert remind_resp.json()["notified"] == 1

    login_resp = client.post("/api/v1/auth/login", json={"email": "parent-reminder@example.com", "password": "Str0ng#Passw0rd!"})
    parent_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    notif_resp = client.get("/api/v1/me/notifications", headers=parent_headers)
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()
    assert len(notifs) == 1
    assert notifs[0]["type"] == "invoice_reminder"
    assert notifs[0]["read_at"] is None
    assert "Fifamè" in notifs[0]["body"]


def test_invoice_reminder_with_no_linked_guardian_returns_zero(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "X", "last_name": "Y"}, headers=headers).json()
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 10000, "due_date": "2026-10-01"},
        headers=headers,
    ).json()
    resp = client.post(f"/api/v1/invoices/{invoice['id']}/remind", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["notified"] == 0


def test_mark_notification_as_read(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 10000, "due_date": "2026-10-01"},
        headers=headers,
    ).json()
    parent = client.post(
        "/api/v1/users",
        json={"email": "parent-read@example.com", "password": "Str0ng#Passw0rd!", "full_name": "Parent", "role": "parent"},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent["id"], "student_id": student["id"], "relationship_label": "Père"},
        headers=headers,
    )
    client.post(f"/api/v1/invoices/{invoice['id']}/remind", headers=headers)

    login_resp = client.post("/api/v1/auth/login", json={"email": "parent-read@example.com", "password": "Str0ng#Passw0rd!"})
    parent_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    notif_id = client.get("/api/v1/me/notifications", headers=parent_headers).json()[0]["id"]

    read_resp = client.post(f"/api/v1/me/notifications/{notif_id}/read", headers=parent_headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["read_at"] is not None


def test_notifications_are_isolated_per_recipient(client, make_tenant, make_user, auth_headers):
    """Un parent ne doit jamais voir les notifications d'un autre destinataire,
    même au sein du même établissement."""
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 10000, "due_date": "2026-10-01"},
        headers=headers,
    ).json()
    parent_a = client.post(
        "/api/v1/users",
        json={"email": "iso-a@example.com", "password": "Str0ng#Passw0rd!", "full_name": "A", "role": "parent"},
        headers=headers,
    ).json()
    parent_b, pwd_b = make_user(tenant=tenant, role=UserRole.PARENT)
    client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": parent_a["id"], "student_id": student["id"], "relationship_label": "Mère"},
        headers=headers,
    )
    client.post(f"/api/v1/invoices/{invoice['id']}/remind", headers=headers)

    b_headers = auth_headers(parent_b, pwd_b)
    b_notifs = client.get("/api/v1/me/notifications", headers=b_headers)
    assert b_notifs.json() == []


def test_teacher_cannot_send_invoice_reminder(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    teacher, pwd_t = make_user(tenant=tenant, role=UserRole.TEACHER)
    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=auth_headers(admin, pwd)).json()
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 10000, "due_date": "2026-10-01"},
        headers=auth_headers(admin, pwd),
    ).json()
    resp = client.post(f"/api/v1/invoices/{invoice['id']}/remind", headers=auth_headers(teacher, pwd_t))
    assert resp.status_code == 403
