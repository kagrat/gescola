from app.models.user import UserRole


# ---------------- Création du compte Direction par le Fondateur ----------------

def test_founder_can_create_school_admin(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    founder, pwd = make_user(tenant=tenant, role=UserRole.FOUNDER)
    resp = client.post(
        "/api/v1/users",
        json={"email": "direction@example.com", "password": "Str0ng#Passw0rd!", "full_name": "M. Le Directeur", "role": "school_admin"},
        headers=auth_headers(founder, pwd),
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "school_admin"


def test_school_admin_cannot_create_another_school_admin(client, make_tenant, make_user, auth_headers):
    """La Direction ne peut pas se cloner ni créer un pair — seul le
    Fondateur a ce pouvoir (asymétrie de la hiérarchie)."""
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    resp = client.post(
        "/api/v1/users",
        json={"email": "autre-direction@example.com", "password": "Str0ng#Passw0rd!", "full_name": "X", "role": "school_admin"},
        headers=auth_headers(admin, pwd),
    )
    assert resp.status_code == 403


def test_nobody_can_create_founder_via_users_endpoint(client, make_tenant, make_user, auth_headers):
    """Le Fondateur n'est créé qu'à la création de l'établissement — jamais
    via /users, même par un Fondateur existant (pas d'ambiguïté sur qui est
    LE fondateur d'un établissement)."""
    tenant = make_tenant()
    founder, pwd = make_user(tenant=tenant, role=UserRole.FOUNDER)
    resp = client.post(
        "/api/v1/users",
        json={"email": "second-fondateur@example.com", "password": "Str0ng#Passw0rd!", "full_name": "X", "role": "founder"},
        headers=auth_headers(founder, pwd),
    )
    assert resp.status_code == 400


def test_founder_can_still_create_other_internal_roles(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    founder, pwd = make_user(tenant=tenant, role=UserRole.FOUNDER)
    headers = auth_headers(founder, pwd)
    for role in ["censor", "supervisor", "accountant", "staff", "teacher", "parent"]:
        resp = client.post(
            "/api/v1/users",
            json={"email": f"{role}@example.com", "password": "Str0ng#Passw0rd!", "full_name": role, "role": role},
            headers=headers,
        )
        assert resp.status_code == 201, f"échec pour le rôle {role}: {resp.text}"


# ---------------- Héritage des permissions de la Direction ----------------

def test_founder_inherits_school_admin_permissions(client, make_tenant, make_user, auth_headers):
    """Vérifie l'héritage sur un échantillon représentatif de domaines
    (registre, notes, finances, personnel) plutôt que de retester
    exhaustivement chaque endpoint déjà couvert pour SCHOOL_ADMIN."""
    tenant = make_tenant()
    founder, pwd = make_user(tenant=tenant, role=UserRole.FOUNDER)
    headers = auth_headers(founder, pwd)

    student_resp = client.post("/api/v1/students", json={"first_name": "A", "last_name": "B"}, headers=headers)
    assert student_resp.status_code == 201
    student = student_resp.json()

    grade_resp = client.post(
        "/api/v1/grades",
        json={"student_id": student["id"], "subject_id": client.post("/api/v1/subjects", json={"name": "Maths"}, headers=headers).json()["id"],
              "term": "T1", "evaluation_label": "D1", "value": 15},
        headers=headers,
    )
    assert grade_resp.status_code == 201

    invoice_resp = client.post(
        "/api/v1/invoices",
        json={"student_id": student["id"], "label": "Scolarité", "amount_due": 10000, "due_date": "2026-12-01"},
        headers=headers,
    )
    assert invoice_resp.status_code == 201

    assert client.get("/api/v1/users", headers=headers).status_code == 200
    assert client.get("/api/v1/reports/overview", headers=headers).status_code == 200
    assert client.get("/api/v1/audit-logs", headers=headers).status_code == 200


# ---------------- Abonnement : exclusivité dynamique du Fondateur ----------------

def test_school_admin_can_view_billing_when_no_founder_exists(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=auth_headers(super_admin, pwd_super))

    resp = client.get("/api/v1/billing/me", headers=auth_headers(admin, pwd))
    assert resp.status_code == 200


def test_school_admin_cannot_view_billing_when_founder_exists(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    make_user(tenant=tenant, role=UserRole.FOUNDER)  # le simple fait qu'il existe suffit
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=auth_headers(super_admin, pwd_super))

    resp = client.get("/api/v1/billing/me", headers=auth_headers(admin, pwd))
    assert resp.status_code == 403


def test_founder_can_always_view_billing(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    founder, pwd = make_user(tenant=tenant, role=UserRole.FOUNDER)
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=auth_headers(super_admin, pwd_super))

    resp = client.get("/api/v1/billing/me", headers=auth_headers(founder, pwd))
    assert resp.status_code == 200
