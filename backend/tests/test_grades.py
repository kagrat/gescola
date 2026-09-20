from app.models.user import UserRole


def _setup_school(make_tenant, make_user, auth_headers, client):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    student = client.post("/api/v1/students", json={"first_name": "Nadège", "last_name": "Houngbo"}, headers=headers).json()
    maths = client.post("/api/v1/subjects", json={"name": "Mathématiques", "default_coefficient": 4}, headers=headers).json()
    francais = client.post("/api/v1/subjects", json={"name": "Français", "default_coefficient": 3}, headers=headers).json()
    return headers, student, maths, francais, admin, pwd


def test_weighted_average_calculation(client, make_tenant, make_user, auth_headers):
    headers, student, maths, francais, _, _ = _setup_school(make_tenant, make_user, auth_headers, client)

    # Maths : deux notes coeff 4 -> moyenne matière = (14+10)/2 = 12
    client.post("/api/v1/grades", json={"student_id": student["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D1", "value": 14, "coefficient": 4}, headers=headers)
    client.post("/api/v1/grades", json={"student_id": student["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D2", "value": 10, "coefficient": 4}, headers=headers)
    # Français : une note coeff 3 -> moyenne matière = 16
    client.post("/api/v1/grades", json={"student_id": student["id"], "subject_id": francais["id"], "term": "T1", "evaluation_label": "D1", "value": 16, "coefficient": 3}, headers=headers)

    resp = client.get(f"/api/v1/students/{student['id']}/average", params={"term": "T1"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject_averages"][maths["id"]] == 12.0
    assert body["subject_averages"][francais["id"]] == 16.0
    # Moyenne générale pondérée par la somme des coefficients de chaque matière :
    # maths pèse 8 (4+4) à 12, français pèse 3 à 16 -> (12*8 + 16*3) / 11 = 13.09
    assert body["general_average"] == 13.09


def test_grade_value_out_of_range_is_rejected(client, make_tenant, make_user, auth_headers):
    headers, student, maths, _, _, _ = _setup_school(make_tenant, make_user, auth_headers, client)
    resp = client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D1", "value": 25},
        headers=headers,
    )
    assert resp.status_code == 422


def test_locked_grade_cannot_be_edited_by_teacher(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd_admin = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    teacher, pwd_teacher = make_user(tenant=tenant, role=UserRole.TEACHER)
    headers_admin = auth_headers(admin, pwd_admin)
    headers_teacher = auth_headers(teacher, pwd_teacher)

    student = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers_admin).json()
    subject = client.post("/api/v1/subjects", json={"name": "SVT"}, headers=headers_admin).json()
    grade = client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "D1", "value": 10},
        headers=headers_teacher,
    ).json()

    lock_resp = client.post(f"/api/v1/students/{student['id']}/grades/lock", params={"term": "T1"}, headers=headers_admin)
    assert lock_resp.json()["locked_count"] == 1

    # Vérification indirecte : la note doit apparaître verrouillée dans la liste
    grades = client.get(f"/api/v1/students/{student['id']}/grades", params={"term": "T1"}, headers=headers_admin).json()
    assert grades[0]["is_locked"] is True

    # L'enseignant ne peut pas modifier une note verrouillée
    teacher_edit = client.patch(f"/api/v1/grades/{grade['id']}", json={"value": 18}, headers=headers_teacher)
    assert teacher_edit.status_code == 403

    # La direction PEUT modifier une note verrouillée, mais l'action est journalisée
    admin_edit = client.patch(f"/api/v1/grades/{grade['id']}", json={"value": 18}, headers=headers_admin)
    assert admin_edit.status_code == 200
    assert admin_edit.json()["value"] == 18.0

    from app.db.session import SessionLocal
    from app.models.audit import AuditLog

    db = SessionLocal()
    try:
        entries = db.query(AuditLog).filter(AuditLog.action == "grade.override_after_lock").all()
        assert len(entries) == 1
        assert entries[0].metadata_json["old_value"] == 10.0
        assert entries[0].metadata_json["new_value"] == 18.0
    finally:
        db.close()
