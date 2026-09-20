from app.models.user import UserRole


def _bootstrap(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    class_a = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème"}, headers=headers).json()
    class_b = client.post("/api/v1/classes", json={"name": "6ème B", "level": "6ème"}, headers=headers).json()
    maths = client.post("/api/v1/subjects", json={"name": "Mathématiques"}, headers=headers).json()
    francais = client.post("/api/v1/subjects", json={"name": "Français"}, headers=headers).json()
    teacher, pwd_teacher = make_user(tenant=tenant, role=UserRole.TEACHER)
    return tenant, headers, class_a, class_b, maths, francais, teacher, pwd_teacher


# ---------------- Affectations enseignant/classe/matière ----------------

def test_create_and_list_teacher_assignment(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)

    resp = client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=headers,
    )
    assert resp.status_code == 201

    listed = client.get("/api/v1/teacher-assignments", headers=headers).json()
    assert len(listed) == 1


def test_duplicate_assignment_rejected(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    payload = {"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]}
    first = client.post("/api/v1/teacher-assignments", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/teacher-assignments", json=payload, headers=headers)
    assert second.status_code == 409


def test_assignment_rejects_non_teacher_role(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, _teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    staff, _pwd2 = make_user(tenant=tenant, role=UserRole.STAFF)
    resp = client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(staff.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=headers,
    )
    assert resp.status_code == 400


def test_staff_cannot_manage_assignments(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    staff, pwd_staff = make_user(tenant=tenant, role=UserRole.STAFF)
    resp = client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=auth_headers(staff, pwd_staff),
    )
    assert resp.status_code == 403


# ---------------- Restriction de la saisie des notes par affectation ----------------

def test_teacher_with_assignment_restricted_to_it(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, class_b, maths, francais, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    teacher_headers = auth_headers(teacher, pwd_teacher)

    client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=headers,
    )

    student_a = client.post("/api/v1/students", json={"first_name": "A", "last_name": "A", "class_id": class_a["id"]}, headers=headers).json()
    student_b = client.post("/api/v1/students", json={"first_name": "B", "last_name": "B", "class_id": class_b["id"]}, headers=headers).json()

    # Autorisé : sa classe, sa matière
    ok_resp = client.post(
        "/api/v1/grades",
        json={"student_id": student_a["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D1", "value": 12},
        headers=teacher_headers,
    )
    assert ok_resp.status_code == 201

    # Refusé : élève d'une classe non assignée
    wrong_class = client.post(
        "/api/v1/grades",
        json={"student_id": student_b["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D1", "value": 12},
        headers=teacher_headers,
    )
    assert wrong_class.status_code == 403

    # Refusé : bonne classe, mauvaise matière
    wrong_subject = client.post(
        "/api/v1/grades",
        json={"student_id": student_a["id"], "subject_id": francais["id"], "term": "T1", "evaluation_label": "D1", "value": 12},
        headers=teacher_headers,
    )
    assert wrong_subject.status_code == 403


def test_teacher_without_any_assignment_is_not_restricted(client, make_tenant, make_user, auth_headers):
    """Grandfathering : un enseignant sans aucune affectation enregistrée
    (établissement pas encore configuré) reste non restreint."""
    tenant, headers, class_a, _class_b, maths, _francais, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    student_a = client.post("/api/v1/students", json={"first_name": "A", "last_name": "A", "class_id": class_a["id"]}, headers=headers).json()

    resp = client.post(
        "/api/v1/grades",
        json={"student_id": student_a["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D1", "value": 12},
        headers=auth_headers(teacher, pwd_teacher),
    )
    assert resp.status_code == 201


def test_school_admin_never_restricted_by_assignments(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    # Une affectation existe pour l'enseignant, mais la Direction reste libre.
    client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=headers,
    )
    student_a = client.post("/api/v1/students", json={"first_name": "A", "last_name": "A", "class_id": class_a["id"]}, headers=headers).json()
    resp = client.post(
        "/api/v1/grades",
        json={"student_id": student_a["id"], "subject_id": maths["id"], "term": "T1", "evaluation_label": "D1", "value": 15},
        headers=headers,
    )
    assert resp.status_code == 201


# ---------------- Emploi du temps ----------------

def test_create_timetable_slot_and_read_by_class_and_teacher(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)

    resp = client.post(
        "/api/v1/timetable",
        json={
            "class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id),
            "day_of_week": "monday", "start_time": "08:00:00", "end_time": "09:00:00", "room": "Salle 3",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    class_view = client.get(f"/api/v1/classes/{class_a['id']}/timetable", headers=headers)
    assert class_view.status_code == 200
    assert len(class_view.json()) == 1

    teacher_view = client.get("/api/v1/users/me/timetable", headers=auth_headers(teacher, pwd_teacher))
    assert teacher_view.status_code == 200
    assert len(teacher_view.json()) == 1


def test_timetable_rejects_class_double_booking(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    other_teacher, _pwd2 = make_user(tenant=tenant, role=UserRole.TEACHER)

    client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id), "day_of_week": "monday", "start_time": "08:00:00", "end_time": "09:00:00"},
        headers=headers,
    )
    # Même classe, même créneau (chevauchement), autre matière/enseignant : refusé
    conflict = client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": francais["id"], "teacher_id": str(other_teacher.id), "day_of_week": "monday", "start_time": "08:30:00", "end_time": "09:30:00"},
        headers=headers,
    )
    assert conflict.status_code == 409


def test_timetable_rejects_teacher_double_booking(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, class_b, maths, francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)

    client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id), "day_of_week": "tuesday", "start_time": "10:00:00", "end_time": "11:00:00"},
        headers=headers,
    )
    # Même enseignant, créneau chevauchant, mais AUTRE classe : refusé aussi
    conflict = client.post(
        "/api/v1/timetable",
        json={"class_id": class_b["id"], "subject_id": francais["id"], "teacher_id": str(teacher.id), "day_of_week": "tuesday", "start_time": "10:30:00", "end_time": "11:30:00"},
        headers=headers,
    )
    assert conflict.status_code == 409


def test_timetable_allows_non_overlapping_slots(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)

    first = client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id), "day_of_week": "wednesday", "start_time": "08:00:00", "end_time": "09:00:00"},
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": francais["id"], "teacher_id": str(teacher.id), "day_of_week": "wednesday", "start_time": "09:00:00", "end_time": "10:00:00"},
        headers=headers,
    )
    assert second.status_code == 201


def test_timetable_invalid_time_range_rejected(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    resp = client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id), "day_of_week": "monday", "start_time": "10:00:00", "end_time": "09:00:00"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_supervisor_cannot_manage_timetable(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    supervisor, pwd_supervisor = make_user(tenant=tenant, role=UserRole.SUPERVISOR)
    resp = client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id), "day_of_week": "monday", "start_time": "08:00:00", "end_time": "09:00:00"},
        headers=auth_headers(supervisor, pwd_supervisor),
    )
    assert resp.status_code == 403


def test_censor_can_manage_timetable(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _francais, teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    censor, pwd_censor = make_user(tenant=tenant, role=UserRole.CENSOR)
    resp = client.post(
        "/api/v1/timetable",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "teacher_id": str(teacher.id), "day_of_week": "monday", "start_time": "08:00:00", "end_time": "09:00:00"},
        headers=auth_headers(censor, pwd_censor),
    )
    assert resp.status_code == 201
