import pyotp

from app.models.user import UserRole


def test_mfa_setup_confirm_and_login_flow(client, make_user, auth_headers):
    user, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(user, pwd)

    setup_resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["secret"]
    assert "provisioning_uri" in setup_resp.json()

    code = pyotp.TOTP(secret).now()
    confirm_resp = client.post("/api/v1/auth/mfa/confirm", json={"code": code}, headers=headers)
    assert confirm_resp.status_code == 204

    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.json()["mfa_enabled"] is True

    # Une connexion classique doit désormais demander le second facteur
    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": pwd})
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["mfa_required"] is True
    assert body["access_token"] is None
    mfa_token = body["mfa_token"]

    # Un mauvais code est refusé
    bad_resp = client.post("/api/v1/auth/mfa/login-verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert bad_resp.status_code == 401

    # Le bon code complète la connexion
    good_code = pyotp.TOTP(secret).now()
    good_resp = client.post("/api/v1/auth/mfa/login-verify", json={"mfa_token": mfa_token, "code": good_code})
    assert good_resp.status_code == 200
    assert "access_token" in good_resp.json()


def test_mfa_setup_requires_confirmation_before_enabled(client, make_user, auth_headers):
    user, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(user, pwd)
    client.post("/api/v1/auth/mfa/setup", headers=headers)

    # Sans confirmation, une connexion classique fonctionne toujours normalement
    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": pwd})
    assert login_resp.status_code == 200
    assert login_resp.json()["mfa_required"] is False
    assert login_resp.json()["access_token"] is not None


def test_mfa_confirm_wrong_code_rejected(client, make_user, auth_headers):
    user, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(user, pwd)
    client.post("/api/v1/auth/mfa/setup", headers=headers)
    resp = client.post("/api/v1/auth/mfa/confirm", json={"code": "000000"}, headers=headers)
    assert resp.status_code == 400


def test_mfa_disable_requires_valid_code(client, make_user, auth_headers):
    user, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(user, pwd)
    setup_resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    client.post("/api/v1/auth/mfa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    bad = client.post("/api/v1/auth/mfa/disable", json={"code": "000000"}, headers=headers)
    assert bad.status_code == 400

    good = client.post("/api/v1/auth/mfa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=headers)
    assert good.status_code == 204

    # Redevient une connexion simple
    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": pwd})
    assert login_resp.json()["mfa_required"] is False


def test_mfa_pending_token_cannot_be_used_as_access_token(client, make_user, auth_headers):
    """Un jeton MFA_PENDING ne doit donner accès à AUCUN endpoint protégé —
    seulement à /auth/mfa/login-verify."""
    user, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(user, pwd)
    setup_resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    client.post("/api/v1/auth/mfa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": pwd})
    mfa_token = login_resp.json()["mfa_token"]

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mfa_token}"})
    assert resp.status_code == 401
