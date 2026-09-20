from app.core.config import Settings
from app.models.user import UserRole


def test_default_login_rate_limit_is_strict_in_absence_of_override():
    """Le test d'intégration ci-dessous assouplit volontairement le rate limit
    (voir conftest.py) pour isoler le test du verrouillage de compte. Ce test
    unitaire vérifie séparément que la valeur PAR DÉFAUT de la configuration
    (celle qui s'appliquerait réellement en production sans variable
    d'environnement LOGIN_RATE_LIMIT) reste stricte."""
    assert Settings.model_fields["LOGIN_RATE_LIMIT"].default == "5/minute"


def test_login_success_returns_token_pair(client, make_user, auth_headers):
    user, password = make_user(role=UserRole.SCHOOL_ADMIN)
    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_generic_401(client, make_user):
    user, _ = make_user(role=UserRole.SCHOOL_ADMIN)
    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"})
    assert resp.status_code == 401
    # Le message doit être générique (pas de fuite "email inconnu" vs "mdp incorrect")
    assert resp.json()["detail"] == "Identifiants invalides."


def test_login_unknown_email_returns_same_generic_401(client):
    resp = client.post("/api/v1/auth/login", json={"email": "inconnu@example.com", "password": "whatever123!X"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Identifiants invalides."


def test_account_locks_after_repeated_failures(client, make_user):
    user, password = make_user(role=UserRole.SCHOOL_ADMIN)
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong"})

    # Le 6e essai, même avec le bon mot de passe, doit être refusé (compte verrouillé)
    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 423


def test_me_requires_valid_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user_identity(client, make_user, auth_headers):
    user, password = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(user, password)
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user.email
    assert body["role"] == "school_admin"


def test_refresh_token_rotates_and_old_one_is_rejected(client, make_user):
    user, password = make_user(role=UserRole.SCHOOL_ADMIN)
    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    old_refresh = login_resp.json()["refresh_token"]

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Rejouer l'ancien refresh token doit désormais échouer (rotation = révocation à l'usage)
    replay_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_resp.status_code == 401
