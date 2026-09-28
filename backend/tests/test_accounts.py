import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import validate_password_strength
from app.db.session import SessionLocal, set_tenant_context
from app.models.user import User, UserRole

PASSWORD = "Str0ng#Passw0rd!"
NEW_PASSWORD = "Nouveau#Passw0rd77"


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _tokens(client, email, password):
    resp = _login(client, email, password)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["refresh_token"]


class Staff:
    """Établissement de test avec Fondateur, Direction, Censeur, enseignant et secrétariat."""


def _school(make_tenant, make_user, auth_headers):
    s = Staff()
    s.tenant = make_tenant()
    s.founder, p = make_user(tenant=s.tenant, role=UserRole.FOUNDER, full_name="M. Fondateur"); s.founder_h = auth_headers(s.founder, p)
    s.admin, p = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN, full_name="Mme Direction"); s.admin_h = auth_headers(s.admin, p)
    s.censor, p = make_user(tenant=s.tenant, role=UserRole.CENSOR, full_name="M. Censeur"); s.censor_h = auth_headers(s.censor, p)
    s.teacher, s.teacher_pwd = make_user(tenant=s.tenant, role=UserRole.TEACHER, full_name="M. Prof")
    s.staff, p = make_user(tenant=s.tenant, role=UserRole.STAFF); s.staff_h = auth_headers(s.staff, p)
    return s


def _audit(client, headers):
    return client.get("/api/v1/audit-logs", headers=headers).json()


# ======================= Mot de passe provisoire et changement de mot de passe =======================

def test_account_created_by_admin_must_change_password_before_anything_else(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    created = client.post("/api/v1/users", json={"email": "nouveau.prof@example.com", "password": PASSWORD, "full_name": "Nouveau Prof", "role": "teacher"}, headers=s.admin_h)
    assert created.status_code == 201 and created.json()["must_change_password"] is True

    headers, _ = _tokens(client, "nouveau.prof@example.com", PASSWORD)
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["must_change_password"] is True and me["full_name"] == "Nouveau Prof"
    blocked = client.get("/api/v1/students", headers=headers)
    assert blocked.status_code == 403 and "nouveau mot de passe" in blocked.json()["detail"]

    change = "/api/v1/auth/change-password"
    wrong = client.post(change, json={"current_password": "Incorrect#Passw0rd1", "new_password": NEW_PASSWORD}, headers=headers)
    assert wrong.status_code == 400                                     # 400 et non 401 : ne déclenche pas le rafraîchissement du client
    assert client.post(change, json={"current_password": PASSWORD, "new_password": "faible"}, headers=headers).status_code == 422
    assert client.post(change, json={"current_password": PASSWORD, "new_password": PASSWORD}, headers=headers).status_code == 400

    ok = client.post(change, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}, headers=headers)
    assert ok.status_code == 200
    fresh = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=fresh).json()["must_change_password"] is False
    assert client.get("/api/v1/students", headers=fresh).status_code == 200


def test_change_password_ends_other_sessions_immediately(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    user, pwd = make_user(tenant=tenant, role=UserRole.TEACHER)
    session_a, refresh_a = _tokens(client, user.email, pwd)
    session_b, refresh_b = _tokens(client, user.email, pwd)
    assert client.get("/api/v1/students", headers=session_b).status_code == 200

    resp = client.post("/api/v1/auth/change-password", json={"current_password": pwd, "new_password": NEW_PASSWORD}, headers=session_a)
    assert resp.status_code == 200

    assert client.get("/api/v1/students", headers=session_b).status_code == 401          # jeton d'accès invalidé à l'instant
    assert client.get("/api/v1/students", headers=session_a).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_b}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_a}).status_code == 401
    assert _login(client, user.email, pwd).status_code == 401                            # ancien mot de passe refusé
    assert client.get("/api/v1/students", headers={"Authorization": f"Bearer {resp.json()['access_token']}"}).status_code == 200
    assert _login(client, user.email, NEW_PASSWORD).status_code == 200


def test_wrong_current_password_counts_toward_lockout(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    user, pwd = make_user(tenant=tenant, role=UserRole.TEACHER)
    headers, _ = _tokens(client, user.email, pwd)
    for _ in range(5):
        assert client.post("/api/v1/auth/change-password", json={"current_password": "Mauvais#Passw0rd9", "new_password": NEW_PASSWORD}, headers=headers).status_code == 400
    assert _login(client, user.email, pwd).status_code == 423   # verrouillé : un jeton volé ne permet pas de deviner le mot de passe


def test_change_password_is_audited_without_secrets(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    headers, _ = _tokens(client, s.teacher.email, s.teacher_pwd)
    client.post("/api/v1/auth/change-password", json={"current_password": s.teacher_pwd, "new_password": NEW_PASSWORD}, headers=headers)
    logs = _audit(client, s.admin_h)
    assert any(log["action"] == "auth.password_changed" for log in logs)
    assert NEW_PASSWORD not in json.dumps(logs) and s.teacher_pwd not in json.dumps(logs)


def test_change_password_requires_authentication(client):
    assert client.post("/api/v1/auth/change-password", json={"current_password": "x", "new_password": NEW_PASSWORD}).status_code == 401


# ======================= Désactivation / réactivation =======================

def test_deactivation_takes_effect_immediately_and_reactivation_restores_login(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    headers, refresh = _tokens(client, s.teacher.email, s.teacher_pwd)
    assert client.get("/api/v1/students", headers=headers).status_code == 200

    off = client.post(f"/api/v1/users/{s.teacher.id}/deactivate", headers=s.admin_h)
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert client.get("/api/v1/students", headers=headers).status_code == 401           # même jeton encore « valide » : refusé
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert _login(client, s.teacher.email, s.teacher_pwd).status_code == 401

    on = client.post(f"/api/v1/users/{s.teacher.id}/reactivate", headers=s.admin_h)
    assert on.status_code == 200 and on.json()["is_active"] is True
    assert client.get("/api/v1/students", headers=headers).status_code == 401           # l'ancienne session ne ressuscite pas
    assert _login(client, s.teacher.email, s.teacher_pwd).status_code == 200

    actions = [log["action"] for log in _audit(client, s.admin_h)]
    assert "user.deactivated" in actions and "user.reactivated" in actions
    assert client.post(f"/api/v1/users/{s.teacher.id}/reactivate", headers=s.admin_h).status_code == 200   # idempotent


def test_reactivation_clears_lockout(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    for _ in range(5):
        _login(client, s.teacher.email, "Mauvais#Passw0rd9")
    assert _login(client, s.teacher.email, s.teacher_pwd).status_code == 423
    client.post(f"/api/v1/users/{s.teacher.id}/deactivate", headers=s.admin_h)
    client.post(f"/api/v1/users/{s.teacher.id}/reactivate", headers=s.admin_h)
    assert _login(client, s.teacher.email, s.teacher_pwd).status_code == 200


# ======================= Hiérarchie et habilitations =======================

def test_nobody_can_act_on_their_own_account(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    for headers, user in ((s.admin_h, s.admin), (s.founder_h, s.founder)):
        for action in ("deactivate", "reset-password", "reset-mfa"):
            assert client.post(f"/api/v1/users/{user.id}/{action}", headers=headers).status_code == 400, action
        assert client.patch(f"/api/v1/users/{user.id}", json={"role": "teacher"}, headers=headers).status_code == 400


def test_founder_account_is_out_of_reach_of_the_school(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    for action in ("deactivate", "reset-password", "reset-mfa"):
        assert client.post(f"/api/v1/users/{s.founder.id}/{action}", headers=s.admin_h).status_code == 403, action
    assert client.patch(f"/api/v1/users/{s.founder.id}", json={"full_name": "Piraté"}, headers=s.admin_h).status_code == 403
    assert client.get("/api/v1/users", headers=s.founder_h).status_code == 200


def test_only_founder_manages_the_direction_account(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    other_admin, _ = make_user(tenant=s.tenant, role=UserRole.SCHOOL_ADMIN)
    for action in ("deactivate", "reset-password", "reset-mfa"):
        assert client.post(f"/api/v1/users/{other_admin.id}/{action}", headers=s.admin_h).status_code == 403, action
    assert client.patch(f"/api/v1/users/{other_admin.id}", json={"full_name": "X"}, headers=s.admin_h).status_code == 403
    assert client.post(f"/api/v1/users/{s.admin.id}/deactivate", headers=s.founder_h).status_code == 200      # le Fondateur, oui


def test_only_direction_and_founder_can_manage_accounts(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    target = s.teacher
    for headers in (s.censor_h, s.staff_h):
        assert client.patch(f"/api/v1/users/{target.id}", json={"full_name": "X"}, headers=headers).status_code == 403
        for action in ("deactivate", "reactivate", "reset-password", "reset-mfa"):
            assert client.post(f"/api/v1/users/{target.id}/{action}", headers=headers).status_code == 403, action


def test_accounts_of_another_school_are_invisible(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    other = make_tenant()
    foreign_admin, p = make_user(tenant=other, role=UserRole.SCHOOL_ADMIN)
    foreign_h = auth_headers(foreign_admin, p)
    assert client.patch(f"/api/v1/users/{s.teacher.id}", json={"full_name": "X"}, headers=foreign_h).status_code == 404
    for action in ("deactivate", "reactivate", "reset-password", "reset-mfa"):
        assert client.post(f"/api/v1/users/{s.teacher.id}/{action}", headers=foreign_h).status_code == 404, action


# ======================= Réinitialisation du mot de passe =======================

def test_admin_reset_gives_a_strong_one_time_password_and_locks_out_old_sessions(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    headers, refresh = _tokens(client, s.teacher.email, s.teacher_pwd)
    for _ in range(5):
        _login(client, s.teacher.email, "Mauvais#Passw0rd9")                                # compte verrouillé
    assert _login(client, s.teacher.email, s.teacher_pwd).status_code == 423

    resp = client.post(f"/api/v1/users/{s.teacher.id}/reset-password", headers=s.admin_h)
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    temporary = resp.json()["temporary_password"]
    assert resp.json()["must_change_password"] is True and validate_password_strength(temporary) == []
    assert len(temporary) >= 14 and not set(temporary) & set("0O1lI")            # dictable sans ambiguïté

    assert client.get("/api/v1/students", headers=headers).status_code == 401                # ancienne session coupée
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert _login(client, s.teacher.email, s.teacher_pwd).status_code == 401                 # ancien mot de passe refusé
    new_headers, _ = _tokens(client, s.teacher.email, temporary)                             # verrou levé, provisoire accepté
    assert client.get("/api/v1/students", headers=new_headers).status_code == 403             # doit d'abord le changer
    assert client.get("/api/v1/auth/me", headers=new_headers).json()["must_change_password"] is True

    logs = _audit(client, s.admin_h)
    assert any(log["action"] == "user.password_reset" for log in logs)
    assert temporary not in json.dumps(logs)                                                 # jamais dans le journal d'audit


def test_temporary_passwords_are_unpredictable():
    from app.services.account_service import generate_temporary_password
    assert len({generate_temporary_password() for _ in range(50)}) == 50


def test_founder_can_reset_the_direction_and_support_can_reset_the_founder(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    assert client.post(f"/api/v1/users/{s.admin.id}/reset-password", headers=s.founder_h).status_code == 200

    support, p = make_user(role=UserRole.SUPER_ADMIN)
    support_h = auth_headers(support, p)
    listed = client.get(f"/api/v1/platform/tenants/{s.tenant.id}/users", headers=support_h)
    assert listed.status_code == 200 and {u["role"] for u in listed.json()} >= {"founder", "school_admin", "teacher"}
    resp = client.post(f"/api/v1/platform/tenants/{s.tenant.id}/users/{s.founder.id}/reset-password", headers=support_h)
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    assert _login(client, s.founder.email, resp.json()["temporary_password"]).status_code == 200
    assert client.get("/api/v1/platform/tenants/" + str(s.tenant.id) + "/users", headers=s.censor_h).status_code == 403   # (le jeton de la Direction est tombé : son mot de passe vient d'être réinitialisé)
    assert client.post(f"/api/v1/platform/tenants/{s.tenant.id}/users/{s.teacher.id}/reset-password", headers=s.censor_h).status_code == 403
    # un compte n'est joignable que via SON établissement
    other = make_tenant()
    assert client.post(f"/api/v1/platform/tenants/{other.id}/users/{s.teacher.id}/reset-password", headers=support_h).status_code == 404


def test_mfa_reset_lets_a_locked_out_person_back_in(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    db = SessionLocal()
    try:
        set_tenant_context(db, str(s.tenant.id))
        teacher = db.get(User, s.teacher.id)
        teacher.mfa_enabled, teacher.mfa_secret = True, "JBSWY3DPEHPK3PXP"
        db.commit()
    finally:
        db.close()
    assert _login(client, s.teacher.email, s.teacher_pwd).json()["mfa_required"] is True     # sans téléphone : bloqué

    resp = client.post(f"/api/v1/users/{s.teacher.id}/reset-mfa", headers=s.admin_h)
    assert resp.status_code == 200 and resp.json()["mfa_enabled"] is False
    assert _login(client, s.teacher.email, s.teacher_pwd).json().get("mfa_required") is False
    assert any(log["action"] == "user.mfa_reset" for log in _audit(client, s.admin_h))


# ======================= Modification d'un compte =======================

def test_update_name_and_email_with_global_uniqueness(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    ok = client.patch(f"/api/v1/users/{s.teacher.id}", json={"full_name": "  M. Nouveau Nom  ", "email": "nouvelle.adresse@example.com"}, headers=s.admin_h)
    assert ok.status_code == 200 and ok.json()["full_name"] == "M. Nouveau Nom" and ok.json()["email"] == "nouvelle.adresse@example.com"
    assert _login(client, "nouvelle.adresse@example.com", s.teacher_pwd).status_code == 200

    assert client.patch(f"/api/v1/users/{s.teacher.id}", json={"email": s.staff.email.upper()}, headers=s.admin_h).status_code == 409   # casse ignorée
    assert client.patch(f"/api/v1/users/{s.teacher.id}", json={"full_name": "   "}, headers=s.admin_h).status_code == 422
    assert client.patch(f"/api/v1/users/{s.teacher.id}", json={"email": "pas-un-email"}, headers=s.admin_h).status_code == 422
    other = make_tenant()
    foreign, _ = make_user(tenant=other, role=UserRole.TEACHER)
    assert client.patch(f"/api/v1/users/{s.teacher.id}", json={"email": foreign.email}, headers=s.admin_h).status_code == 409           # même dans un autre établissement
    assert "user.updated" in [log["action"] for log in _audit(client, s.admin_h)]


def test_direction_can_edit_own_name_but_not_own_role(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    assert client.patch(f"/api/v1/users/{s.admin.id}", json={"full_name": "Mme Nouvelle Direction"}, headers=s.admin_h).status_code == 200
    assert client.patch(f"/api/v1/users/{s.admin.id}", json={"role": "teacher"}, headers=s.admin_h).status_code == 400


def test_role_change_rules_and_immediate_effect(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    teacher_h, _ = _tokens(client, s.teacher.email, s.teacher_pwd)
    assert client.get("/api/v1/students", headers=teacher_h).status_code == 200

    # Promotion en Censeur : les droits changent tout de suite (jeton émis avec l'ancien rôle refusé).
    up = client.patch(f"/api/v1/users/{s.teacher.id}", json={"role": "censor"}, headers=s.admin_h)
    assert up.status_code == 200 and up.json()["role"] == "censor"
    assert client.get("/api/v1/students", headers=teacher_h).status_code == 401
    censor_h, _ = _tokens(client, s.teacher.email, s.teacher_pwd)
    assert client.get("/api/v1/teachers", headers=censor_h).status_code == 200                 # droits de censeur effectifs

    assert client.patch(f"/api/v1/users/{s.staff.id}", json={"role": "school_admin"}, headers=s.admin_h).status_code == 403      # seul le Fondateur
    assert client.patch(f"/api/v1/users/{s.staff.id}", json={"role": "school_admin"}, headers=s.founder_h).status_code == 200
    assert client.patch(f"/api/v1/users/{s.staff.id}", json={"role": "founder"}, headers=s.founder_h).status_code == 400
    assert client.patch(f"/api/v1/users/{s.staff.id}", json={"role": "super_admin"}, headers=s.founder_h).status_code == 400
    parent = client.post("/api/v1/users", json={"email": "un.parent@example.com", "password": PASSWORD, "full_name": "Parent", "role": "parent"}, headers=s.admin_h).json()
    assert client.patch(f"/api/v1/users/{parent['id']}", json={"role": "teacher"}, headers=s.admin_h).status_code == 400          # parent ↔ personnel : non
    assert client.patch(f"/api/v1/users/{s.censor.id}", json={"role": "parent"}, headers=s.admin_h).status_code == 400


# ======================= Unicité globale des e-mails (bug corrigé) =======================

def test_same_email_cannot_exist_in_two_schools(client, make_tenant, make_user, auth_headers):
    """Avant correction : les deux comptes étaient créés puis la connexion plantait (erreur serveur) pour les deux."""
    a, b = make_tenant(), make_tenant()
    admin_a, pa = make_user(tenant=a, role=UserRole.SCHOOL_ADMIN)
    admin_b, pb = make_user(tenant=b, role=UserRole.SCHOOL_ADMIN)
    body = {"email": "meme.adresse@example.com", "password": PASSWORD, "full_name": "X", "role": "teacher"}
    assert client.post("/api/v1/users", json=body, headers=auth_headers(admin_a, pa)).status_code == 201
    assert client.post("/api/v1/users", json=body, headers=auth_headers(admin_b, pb)).status_code == 409
    assert client.post("/api/v1/users", json={**body, "email": "MEME.Adresse@Example.com"}, headers=auth_headers(admin_b, pb)).status_code == 409
    assert _login(client, "meme.adresse@example.com", PASSWORD).status_code == 200
    assert _login(client, "MEME.ADRESSE@example.com", PASSWORD).status_code == 200            # connexion insensible à la casse


def test_signup_and_tenant_creation_respect_global_email_uniqueness(client, make_tenant, make_user, auth_headers):
    existing, _ = make_user(tenant=make_tenant(), role=UserRole.TEACHER)
    signup = client.post("/api/v1/auth/signup", json={
        "school_name": "École Doublon", "admin_full_name": "X", "admin_email": existing.email.upper(), "admin_password": PASSWORD})
    assert signup.status_code == 409
    support, p = make_user(role=UserRole.SUPER_ADMIN)
    created = client.post("/api/v1/tenants", json={
        "name": "École Doublon", "code": "ecole-doublon", "admin_full_name": "X", "admin_email": existing.email, "admin_password": PASSWORD},
        headers=auth_headers(support, p))
    assert created.status_code == 409


def test_database_itself_refuses_case_insensitive_duplicate_emails(make_tenant, make_user):
    """Garantie en base (index unique sur lower(email)), au-delà des contrôles applicatifs."""
    tenant = make_tenant()
    make_user(tenant=tenant, role=UserRole.TEACHER, email="unique@example.com")
    with pytest.raises(IntegrityError):
        make_user(tenant=make_tenant(), role=UserRole.TEACHER, email="UNIQUE@example.com")


def test_provisional_flag_is_set_for_accounts_chosen_by_someone_else(client, make_tenant, make_user, auth_headers):
    support, p = make_user(role=UserRole.SUPER_ADMIN)
    created = client.post("/api/v1/tenants", json={
        "name": "École Neuve", "code": "ecole-neuve", "admin_full_name": "Le Fondateur", "admin_email": "fondateur.neuf@example.com",
        "admin_password": PASSWORD}, headers=auth_headers(support, p))
    assert created.status_code == 201
    headers, _ = _tokens(client, "fondateur.neuf@example.com", PASSWORD)
    assert client.get("/api/v1/auth/me", headers=headers).json()["must_change_password"] is True      # mot de passe saisi par le Super Admin

    signup = client.post("/api/v1/auth/signup", json={
        "school_name": "École Libre", "admin_full_name": "Fondateur Libre", "admin_email": "fondateur.libre@example.com", "admin_password": PASSWORD})
    assert signup.status_code == 201
    own_h = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=own_h).json()["must_change_password"] is False       # il a choisi son propre mot de passe


def test_deactivated_account_cannot_be_designated_as_bulletin_signer_and_direction_keeps_working(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    client.post(f"/api/v1/users/{s.censor.id}/deactivate", headers=s.admin_h)
    resp = client.patch("/api/v1/establishment/settings", json={"bulletin_censor_user_id": str(s.censor.id)}, headers=s.admin_h)
    assert resp.status_code == 400                                                         # « Ce compte est désactivé. »
    assert client.get("/api/v1/users", headers=s.admin_h).status_code == 200


def test_user_list_exposes_account_state(client, make_tenant, make_user, auth_headers):
    s = _school(make_tenant, make_user, auth_headers)
    client.post(f"/api/v1/users/{s.teacher.id}/deactivate", headers=s.admin_h)
    rows = {u["id"]: u for u in client.get("/api/v1/users", headers=s.admin_h).json()}
    assert rows[str(s.teacher.id)]["is_active"] is False and rows[str(s.admin.id)]["is_active"] is True
    assert {"must_change_password", "mfa_enabled"} <= set(rows[str(s.admin.id)])
