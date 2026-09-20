from app.models.user import UserRole


def test_invoice_and_partial_then_full_payment_flow(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd_admin = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    accountant, pwd_acc = make_user(tenant=tenant, role=UserRole.ACCOUNTANT)
    headers_admin = auth_headers(admin, pwd_admin)
    headers = auth_headers(accountant, pwd_acc)

    student = client.post("/api/v1/students", json={"first_name": "Edwige", "last_name": "Toko"}, headers=headers_admin).json()
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité T1", "amount_due": 100000, "due_date": "2026-10-01"},
        headers=headers,
    ).json()
    assert invoice["status"] == "pending"
    assert invoice["balance"] == 100000.0

    pay1 = client.post(
        "/api/v1/payments", json={"invoice_id": invoice["id"], "amount": 40000, "method": "mobile_money", "reference": "MOMO-1"},
        headers=headers,
    )
    assert pay1.status_code == 201

    listed = client.get(f"/api/v1/students/{student['id']}/invoices", headers=headers).json()
    assert listed[0]["status"] == "partially_paid"
    assert listed[0]["amount_paid"] == 40000.0
    assert listed[0]["balance"] == 60000.0

    pay2 = client.post(
        "/api/v1/payments", json={"invoice_id": invoice["id"], "amount": 60000, "method": "cash"}, headers=headers
    )
    assert pay2.status_code == 201

    listed2 = client.get(f"/api/v1/students/{student['id']}/invoices", headers=headers).json()
    assert listed2[0]["status"] == "paid"
    assert listed2[0]["balance"] == 0.0


def test_negative_amount_rejected(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd_admin = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    accountant, pwd_acc = make_user(tenant=tenant, role=UserRole.ACCOUNTANT)
    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=auth_headers(admin, pwd_admin)).json()
    resp = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": -500, "due_date": "2026-10-01"},
        headers=auth_headers(accountant, pwd_acc),
    )
    assert resp.status_code == 422


def test_teacher_cannot_access_finance_endpoints(client, make_user, auth_headers):
    teacher, pwd = make_user(role=UserRole.TEACHER)
    headers = auth_headers(teacher, pwd)
    resp = client.post(
        "/api/v1/invoices",
        json={"student_id": "00000000-0000-0000-0000-000000000000", "label": "x", "amount_due": 1000, "due_date": "2026-10-01"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_staff_secretariat_cannot_access_finance_endpoints(client, make_user, auth_headers):
    """Le secrétariat gère les inscriptions, pas les finances — rôle du comptable."""
    staff, pwd = make_user(role=UserRole.STAFF)
    headers = auth_headers(staff, pwd)
    resp = client.post(
        "/api/v1/invoices",
        json={"student_id": "00000000-0000-0000-0000-000000000000", "label": "x", "amount_due": 1000, "due_date": "2026-10-01"},
        headers=headers,
    )
    assert resp.status_code == 403
