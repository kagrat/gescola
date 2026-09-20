from app.models.user import UserRole


def test_overview_report_aggregates_finance_attendance_and_grades(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    school_class = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème"}, headers=headers).json()
    subject = client.post("/api/v1/subjects", json={"name": "Maths"}, headers=headers).json()
    student = client.post(
        "/api/v1/students", json={"first_name": "A", "last_name": "B", "class_id": school_class["id"]}, headers=headers
    ).json()

    client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 16},
        headers=headers,
    )
    client.post("/api/v1/attendance", json={"student_id": student["id"], "date": "2026-10-05", "status": "present"}, headers=headers)
    client.post("/api/v1/attendance", json={"student_id": student["id"], "date": "2026-10-06", "status": "absent", "justified": False}, headers=headers)
    invoice = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 30000, "due_date": "2026-10-01"},
        headers=headers,
    ).json()
    client.post("/api/v1/payments", json={"invoice_id": invoice["id"], "amount": 10000, "method": "cash"}, headers=headers)

    report = client.get("/api/v1/reports/overview", params={"term": "T1"}, headers=headers)
    assert report.status_code == 200
    data = report.json()

    assert data["total_active_students"] == 1
    assert data["finance"]["amount_due_total"] == 30000.0
    assert data["finance"]["amount_paid_total"] == 10000.0
    assert data["finance"]["outstanding_total"] == 20000.0
    assert data["attendance"]["records_count"] == 2
    assert data["attendance"]["unjustified_absences"] == 1
    assert data["attendance"]["attendance_rate_percent"] == 50.0
    assert data["average_by_class"]["6ème A"] == 16.0


def test_only_school_admin_can_view_overview_report(client, make_user, auth_headers):
    accountant, pwd = make_user(role=UserRole.ACCOUNTANT)
    resp = client.get("/api/v1/reports/overview", headers=auth_headers(accountant, pwd))
    assert resp.status_code == 403


def test_audit_log_records_and_lists_sensitive_actions(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    subject = client.post("/api/v1/subjects", json={"name": "Maths"}, headers=headers).json()
    client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 10},
        headers=headers,
    )
    client.post(f"/api/v1/students/{student['id']}/grades/lock", params={"term": "T1"}, headers=headers)

    logs_resp = client.get("/api/v1/audit-logs", headers=headers)
    assert logs_resp.status_code == 200
    actions = {log["action"] for log in logs_resp.json()}
    assert "auth.login_success" in actions
    assert "grade.lock_term" in actions


def test_audit_log_is_isolated_per_tenant(client, make_tenant, make_user, auth_headers):
    tenant_a = make_tenant()
    tenant_b = make_tenant()
    admin_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.SCHOOL_ADMIN)
    admin_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SCHOOL_ADMIN)

    client.post("/api/v1/students", json={"first_name": "B-only", "last_name": "X"}, headers=auth_headers(admin_b, pwd_b))

    logs_a = client.get("/api/v1/audit-logs", headers=auth_headers(admin_a, pwd_a)).json()
    bodies = [str(log) for log in logs_a]
    assert not any("B-only" in b for b in bodies)


def test_only_school_admin_can_view_audit_logs(client, make_user, auth_headers):
    teacher, pwd = make_user(role=UserRole.TEACHER)
    resp = client.get("/api/v1/audit-logs", headers=auth_headers(teacher, pwd))
    assert resp.status_code == 403
