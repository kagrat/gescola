from app.models.user import UserRole

TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_super_admin_creates_tenant_with_admin_account_in_one_step(client, make_user, auth_headers):
    super_admin, pwd = make_user(role=UserRole.SUPER_ADMIN)
    headers = auth_headers(super_admin, pwd)

    resp = client.post(
        "/api/v1/tenants",
        json={
            "name": "École Complète", "code": "ecole-complete",
            "admin_full_name": "Mme Directrice", "admin_email": "direction@ecole-complete.bj",
            "admin_password": "Str0ng#Passw0rd!",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    # Le compte Direction créé fonctionne immédiatement
    login = client.post("/api/v1/auth/login", json={"email": "direction@ecole-complete.bj", "password": "Str0ng#Passw0rd!"})
    assert login.status_code == 200

    # Un essai gratuit a démarré automatiquement, comme pour l'inscription en libre-service
    sub = client.get(f"/api/v1/platform/tenants/{resp.json()['id']}/subscription", headers=headers)
    assert sub.status_code == 200
    assert sub.json()["status"] == "trialing"


def test_tenant_creation_rejects_duplicate_admin_email(client, make_user, auth_headers):
    super_admin, pwd = make_user(role=UserRole.SUPER_ADMIN)
    headers = auth_headers(super_admin, pwd)
    payload = {
        "name": "École X", "code": "ecole-x",
        "admin_full_name": "Y", "admin_email": "dup-admin@example.com", "admin_password": "Str0ng#Passw0rd!",
    }
    first = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/tenants", json={**payload, "code": "ecole-y"}, headers=headers)
    assert second.status_code == 409


# ---------------- Paramètres d'établissement ----------------

def test_school_admin_can_update_establishment_settings(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    resp = client.patch(
        "/api/v1/establishment/settings",
        json={"trade_name": "Groupe Scolaire La Colombe", "rccm": "BJ-COT-2024-B-1234", "ifu": "3202400001234", "address": "Cotonou, Bénin", "logo_base64": TINY_PNG},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rccm"] == "BJ-COT-2024-B-1234"
    assert body["logo_base64"] == TINY_PNG

    get_resp = client.get("/api/v1/establishment/settings", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["ifu"] == "3202400001234"


def test_teacher_can_read_but_not_update_establishment_settings(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    teacher, pwd = make_user(tenant=tenant, role=UserRole.TEACHER)
    headers = auth_headers(teacher, pwd)

    assert client.get("/api/v1/establishment/settings", headers=headers).status_code == 200
    resp = client.patch("/api/v1/establishment/settings", json={"rccm": "X"}, headers=headers)
    assert resp.status_code == 403


def test_invalid_logo_format_rejected(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    resp = client.patch(
        "/api/v1/establishment/settings", json={"logo_base64": "not-a-data-uri"}, headers=auth_headers(admin, pwd)
    )
    assert resp.status_code == 422


# ---------------- Signature et tampon personnels ----------------

def test_any_user_can_set_own_signature_and_stamp(client, make_user, auth_headers):
    teacher, pwd = make_user(role=UserRole.TEACHER)
    headers = auth_headers(teacher, pwd)

    resp = client.patch(
        "/api/v1/users/me/signature", json={"signature_base64": TINY_PNG, "stamp_base64": TINY_PNG}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["signature_base64"] == TINY_PNG

    get_resp = client.get("/api/v1/users/me/signature", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["stamp_base64"] == TINY_PNG


def test_signature_is_strictly_personal(client, make_tenant, make_user, auth_headers):
    """Un utilisateur ne peut modifier que SA PROPRE signature — il n'existe
    même pas de route permettant de cibler un autre utilisateur."""
    tenant = make_tenant()
    teacher_a, pwd_a = make_user(tenant=tenant, role=UserRole.TEACHER)
    teacher_b, pwd_b = make_user(tenant=tenant, role=UserRole.TEACHER)

    client.patch("/api/v1/users/me/signature", json={"signature_base64": TINY_PNG}, headers=auth_headers(teacher_a, pwd_a))

    b_signature = client.get("/api/v1/users/me/signature", headers=auth_headers(teacher_b, pwd_b))
    assert b_signature.json()["signature_base64"] is None


def test_invalid_signature_format_rejected(client, make_user, auth_headers):
    teacher, pwd = make_user(role=UserRole.TEACHER)
    resp = client.patch("/api/v1/users/me/signature", json={"signature_base64": "plain-text"}, headers=auth_headers(teacher, pwd))
    assert resp.status_code == 422
