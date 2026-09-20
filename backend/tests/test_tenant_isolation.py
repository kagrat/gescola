"""
Test le plus critique du projet : une fuite de données entre établissements
est classée risque "Critique" en section 9 du cahier des charges. On vérifie
l'isolation à DEUX niveaux :

  1. Niveau API : un utilisateur de l'établissement A ne peut ni lister ni
     consulter par ID une ressource de l'établissement B (404, jamais 403,
     pour ne même pas confirmer l'existence de la ressource).
  2. Niveau base de données : même en contournant complètement la couche
     applicative (requête SQL directe avec le contexte tenant positionné),
     PostgreSQL (policy RLS) refuse de renvoyer les lignes d'un autre tenant.
     Ce second niveau est ce qui protège contre un bug futur qui oublierait
     un filtre tenant_id côté application.
"""
import uuid

from sqlalchemy import text

from app.models.user import UserRole


def test_school_admin_cannot_list_students_of_another_tenant(client, make_tenant, make_user, auth_headers):
    tenant_a = make_tenant(name="École A")
    tenant_b = make_tenant(name="École B")

    admin_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.SCHOOL_ADMIN)
    admin_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SCHOOL_ADMIN)

    headers_b = auth_headers(admin_b, pwd_b)
    create_resp = client.post(
        "/api/v1/students", json={"first_name": "Aïcha", "last_name": "Dossou"}, headers=headers_b
    )
    assert create_resp.status_code == 201
    student_b_id = create_resp.json()["id"]

    headers_a = auth_headers(admin_a, pwd_a)
    list_resp = client.get("/api/v1/students", headers=headers_a)
    assert list_resp.status_code == 200
    assert list_resp.json() == []  # l'élève de B n'apparaît jamais côté A

    direct_resp = client.get(f"/api/v1/students/{student_b_id}", headers=headers_a)
    assert direct_resp.status_code == 404  # jamais 403 : ne pas confirmer l'existence


def test_grades_are_isolated_across_tenants(client, make_tenant, make_user, auth_headers):
    tenant_a = make_tenant(name="École A")
    tenant_b = make_tenant(name="École B")
    admin_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.SCHOOL_ADMIN)
    admin_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SCHOOL_ADMIN)
    teacher_b, pwd_teacher_b = make_user(tenant=tenant_b, role=UserRole.TEACHER)

    headers_admin_b = auth_headers(admin_b, pwd_b)
    headers_teacher_b = auth_headers(teacher_b, pwd_teacher_b)

    student = client.post("/api/v1/students", json={"first_name": "Kokou", "last_name": "Ahouansou"}, headers=headers_admin_b).json()
    subject = client.post("/api/v1/subjects", json={"name": "Mathématiques"}, headers=headers_admin_b).json()
    grade_resp = client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": subject["id"], "term": "T1", "evaluation_label": "Devoir 1", "value": 15},
        headers=headers_teacher_b,
    )
    assert grade_resp.status_code == 201

    # L'admin de l'établissement A ne peut même pas consulter l'élève (404 avant d'atteindre les notes)
    headers_a = auth_headers(admin_a, pwd_a)
    resp = client.get(f"/api/v1/students/{student['id']}/grades", headers=headers_a)
    assert resp.status_code == 404


def test_row_level_security_blocks_cross_tenant_read_at_db_level(make_tenant, tenant_db_session):
    """Contourne volontairement la couche applicative pour prouver que la
    protection tient même en cas d'oubli d'un filtre tenant_id dans un futur
    endpoint : requête SQL directe, avec seulement le contexte RLS positionné."""
    from app.models.student import Student

    tenant_a = make_tenant(name="École A")
    tenant_b = make_tenant(name="École B")

    db_a = tenant_db_session(tenant_a.id)
    db_a.add(Student(tenant_id=tenant_a.id, first_name="Fifamè", last_name="Zinsou"))
    db_a.commit()
    db_a.close()

    db_b = tenant_db_session(tenant_b.id)
    db_b.add(Student(tenant_id=tenant_b.id, first_name="Yao", last_name="Kponou"))
    db_b.commit()
    db_b.close()

    # Requête SQL brute, SANS clause WHERE tenant_id — c'est exactement le cas
    # d'un bug applicatif qui oublierait le filtre. Le contexte RLS doit à lui
    # seul empêcher de voir les lignes de l'autre tenant.
    session_scoped_as_a = tenant_db_session(tenant_a.id)
    rows = session_scoped_as_a.execute(text("SELECT first_name FROM students")).fetchall()
    session_scoped_as_a.close()

    names = {r[0] for r in rows}
    assert names == {"Fifamè"}
    assert "Yao" not in names


def test_row_level_security_blocks_cross_tenant_write_at_db_level(make_tenant, tenant_db_session):
    """Une tentative d'INSERT avec un tenant_id différent du contexte de
    session positionné doit être rejetée par la policy WITH CHECK."""
    from app.models.student import Student

    tenant_a = make_tenant(name="École A")
    tenant_b = make_tenant(name="École B")

    db_a = tenant_db_session(tenant_a.id)
    # Tentative d'écriture d'une ligne appartenant à B alors que le contexte
    # de session est positionné sur A : doit échouer (violation de policy RLS).
    db_a.add(Student(tenant_id=tenant_b.id, first_name="Intrusion", last_name="Test"))
    try:
        db_a.commit()
        raised = False
    except Exception:
        db_a.rollback()
        raised = True
    finally:
        db_a.close()

    assert raised, "La policy RLS aurait dû rejeter l'insertion d'une ligne hors du tenant courant."


def test_no_tenant_context_sees_nothing(make_tenant, tenant_db_session):
    """Sans contexte tenant positionné (valeur sentinelle), aucune ligne d'aucun
    établissement ne doit être visible — pas de fuite par défaut ouvert."""
    from app.models.student import Student

    tenant_a = make_tenant(name="École A")
    db_a = tenant_db_session(tenant_a.id)
    db_a.add(Student(tenant_id=tenant_a.id, first_name="Test", last_name="Élève"))
    db_a.commit()
    db_a.close()

    db_none = tenant_db_session(None)  # équivalent à "aucun tenant" (sentinelle)
    rows = db_none.execute(text("SELECT first_name FROM students")).fetchall()
    db_none.close()
    assert rows == []
