from app.models.user import UserRole


def _bootstrap(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    class_a = client.post("/api/v1/classes", json={"name": "6ème A", "level": "6ème"}, headers=headers).json()
    class_b = client.post("/api/v1/classes", json={"name": "6ème B", "level": "6ème"}, headers=headers).json()
    maths = client.post("/api/v1/subjects", json={"name": "Mathématiques"}, headers=headers).json()
    teacher, pwd_teacher = make_user(tenant=tenant, role=UserRole.TEACHER)
    return tenant, headers, class_a, class_b, maths, teacher, pwd_teacher


# ---------------- Cahier de texte ----------------

def test_teacher_creates_and_lists_lesson_log_entry(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    teacher_headers = auth_headers(teacher, pwd_teacher)

    resp = client.post(
        "/api/v1/lesson-log",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "session_date": "2026-10-05", "content": "Théorème de Pythagore, exercices 1 à 5."},
        headers=teacher_headers,
    )
    assert resp.status_code == 201
    entry = resp.json()

    listed = client.get(f"/api/v1/classes/{class_a['id']}/lesson-log", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["content"] == "Théorème de Pythagore, exercices 1 à 5."

    update_resp = client.patch(f"/api/v1/lesson-log/{entry['id']}", json={"content": "Corrigé"}, headers=teacher_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["content"] == "Corrigé"


def test_lesson_log_respects_teacher_assignment_restriction(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, class_b, maths, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=headers,
    )
    resp = client.post(
        "/api/v1/lesson-log",
        json={"class_id": class_b["id"], "subject_id": maths["id"], "session_date": "2026-10-05", "content": "Hors affectation"},
        headers=auth_headers(teacher, pwd_teacher),
    )
    assert resp.status_code == 403


def test_teacher_cannot_edit_another_teachers_lesson_log_entry(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    other_teacher, pwd_other = make_user(tenant=tenant, role=UserRole.TEACHER)

    entry = client.post(
        "/api/v1/lesson-log",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "session_date": "2026-10-05", "content": "Contenu original"},
        headers=auth_headers(teacher, pwd_teacher),
    ).json()

    resp = client.patch(f"/api/v1/lesson-log/{entry['id']}", json={"content": "Modifié par un autre"}, headers=auth_headers(other_teacher, pwd_other))
    assert resp.status_code == 403


def test_supervisor_cannot_read_lesson_log(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, _maths, _teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    supervisor, pwd_supervisor = make_user(tenant=tenant, role=UserRole.SUPERVISOR)
    resp = client.get(f"/api/v1/classes/{class_a['id']}/lesson-log", headers=auth_headers(supervisor, pwd_supervisor))
    assert resp.status_code == 403


# ---------------- Devoirs ----------------

def test_teacher_creates_homework_and_parent_sees_it(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)

    student = client.post(
        "/api/v1/students", json={"first_name": "Aïcha", "last_name": "Diallo", "class_id": class_a["id"]}, headers=headers
    ).json()
    parent, pwd_parent = make_user(tenant=tenant, role=UserRole.PARENT)
    client.post(
        "/api/v1/guardian-links",
        json={"parent_user_id": str(parent.id), "student_id": student["id"], "relationship_label": "Mère"},
        headers=headers,
    )

    hw_resp = client.post(
        "/api/v1/homework",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "title": "Exercices chapitre 3", "description": "Faire les exercices 1 à 10 p.42", "due_date": "2026-10-10"},
        headers=auth_headers(teacher, pwd_teacher),
    )
    assert hw_resp.status_code == 201

    class_listing = client.get(f"/api/v1/classes/{class_a['id']}/homework", headers=headers)
    assert class_listing.status_code == 200
    assert len(class_listing.json()) == 1

    parent_listing = client.get(f"/api/v1/children/{student['id']}/homework", headers=auth_headers(parent, pwd_parent))
    assert parent_listing.status_code == 200
    assert parent_listing.json()[0]["title"] == "Exercices chapitre 3"


def test_parent_cannot_see_homework_of_unlinked_child(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    student = client.post(
        "/api/v1/students", json={"first_name": "X", "last_name": "Y", "class_id": class_a["id"]}, headers=headers
    ).json()
    client.post(
        "/api/v1/homework",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "title": "Devoir", "description": "Description", "due_date": "2026-10-10"},
        headers=auth_headers(teacher, pwd_teacher),
    )
    unrelated_parent, pwd_unrelated = make_user(tenant=tenant, role=UserRole.PARENT)
    resp = client.get(f"/api/v1/children/{student['id']}/homework", headers=auth_headers(unrelated_parent, pwd_unrelated))
    assert resp.status_code == 404


def test_homework_respects_teacher_assignment_restriction(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, class_b, maths, teacher, pwd_teacher = _bootstrap(client, make_tenant, make_user, auth_headers)
    client.post(
        "/api/v1/teacher-assignments",
        json={"teacher_id": str(teacher.id), "class_id": class_a["id"], "subject_id": maths["id"]},
        headers=headers,
    )
    resp = client.post(
        "/api/v1/homework",
        json={"class_id": class_b["id"], "subject_id": maths["id"], "title": "Hors affectation", "description": "X", "due_date": "2026-10-10"},
        headers=auth_headers(teacher, pwd_teacher),
    )
    assert resp.status_code == 403


def test_staff_can_read_but_not_create_homework(client, make_tenant, make_user, auth_headers):
    tenant, headers, class_a, _class_b, maths, _teacher, _pwd = _bootstrap(client, make_tenant, make_user, auth_headers)
    staff, pwd_staff = make_user(tenant=tenant, role=UserRole.STAFF)
    staff_headers = auth_headers(staff, pwd_staff)

    assert client.get(f"/api/v1/classes/{class_a['id']}/homework", headers=staff_headers).status_code == 200
    resp = client.post(
        "/api/v1/homework",
        json={"class_id": class_a["id"], "subject_id": maths["id"], "title": "X", "description": "Y", "due_date": "2026-10-10"},
        headers=staff_headers,
    )
    assert resp.status_code == 403
