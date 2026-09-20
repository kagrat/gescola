from app.models.user import UserRole


def test_canteen_subscription_generates_invoice(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    plan = client.post("/api/v1/canteen/plans", json={"name": "5 jours/semaine", "price_per_month": 15000}, headers=headers).json()

    sub_resp = client.post(
        "/api/v1/canteen/subscriptions",
        json={"student_id": student["id"], "plan_id": plan["id"], "month": "2026-11"},
        headers=headers,
    )
    assert sub_resp.status_code == 201
    subscription = sub_resp.json()
    assert subscription["status"] == "active"

    invoices = client.get(f"/api/v1/students/{student['id']}/invoices", headers=headers).json()
    matching = [i for i in invoices if i["id"] == subscription["invoice_id"]]
    assert len(matching) == 1
    assert matching[0]["amount_due"] == 15000.0
    assert "Cantine" in matching[0]["label"]


def test_duplicate_canteen_subscription_same_month_rejected(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    plan = client.post("/api/v1/canteen/plans", json={"name": "Ponctuel", "price_per_month": 8000}, headers=headers).json()
    payload = {"student_id": student["id"], "plan_id": plan["id"], "month": "2026-11"}
    first = client.post("/api/v1/canteen/subscriptions", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/canteen/subscriptions", json=payload, headers=headers)
    assert second.status_code == 409


def test_staff_cannot_manage_canteen(client, make_user, auth_headers):
    """La cantine génère des factures — réservé à la direction/comptable, pas au secrétariat."""
    staff, pwd = make_user(role=UserRole.STAFF)
    resp = client.post("/api/v1/canteen/plans", json={"name": "X", "price_per_month": 1000}, headers=auth_headers(staff, pwd))
    assert resp.status_code == 403


def test_library_loan_and_return_flow(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    staff, pwd = make_user(tenant=tenant, role=UserRole.STAFF)
    headers = auth_headers(staff, pwd)

    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    book = client.post(
        "/api/v1/library/books",
        json={"title": "Le Petit Prince", "author": "Saint-Exupéry", "total_copies": 1},
        headers=headers,
    ).json()
    assert book["available_copies"] == 1

    loan_resp = client.post(
        "/api/v1/library/loans", json={"book_id": book["id"], "student_id": student["id"], "due_at": "2026-11-20"}, headers=headers
    )
    assert loan_resp.status_code == 201
    loan = loan_resp.json()
    assert loan["returned_at"] is None

    # Plus de copie disponible pour un second emprunt
    second_loan = client.post(
        "/api/v1/library/loans", json={"book_id": book["id"], "student_id": student["id"], "due_at": "2026-11-20"}, headers=headers
    )
    assert second_loan.status_code == 400

    books_after = client.get("/api/v1/library/books", headers=headers).json()
    assert books_after[0]["available_copies"] == 0

    return_resp = client.post(f"/api/v1/library/loans/{loan['id']}/return", headers=headers)
    assert return_resp.status_code == 200
    assert return_resp.json()["returned_at"] is not None

    books_returned = client.get("/api/v1/library/books", headers=headers).json()
    assert books_returned[0]["available_copies"] == 1


def test_library_loans_isolated_across_tenants(client, make_tenant, make_user, auth_headers):
    tenant_a = make_tenant()
    tenant_b = make_tenant()
    staff_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.STAFF)
    staff_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.STAFF)

    book_b = client.post(
        "/api/v1/library/books", json={"title": "Livre B", "author": "X", "total_copies": 2}, headers=auth_headers(staff_b, pwd_b)
    ).json()

    books_seen_by_a = client.get("/api/v1/library/books", headers=auth_headers(staff_a, pwd_a)).json()
    assert all(b["id"] != book_b["id"] for b in books_seen_by_a)
