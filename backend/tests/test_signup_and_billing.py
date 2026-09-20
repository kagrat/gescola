from datetime import date, timedelta

from app.db.session import SessionLocal
from app.models.billing import Subscription, SubscriptionStatus
from app.models.user import UserRole


# ---------------- Inscription en libre-service ----------------

def test_signup_creates_tenant_admin_and_trial_subscription(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "school_name": "École Nouvelle Génération",
            "admin_full_name": "Mme Directrice",
            "admin_email": "direction@nouvelle-generation.bj",
            "admin_password": "Str0ng#Passw0rd!",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["tenant_id"]
    # Essai de 14 jours par défaut
    trial_end = date.fromisoformat(body["trial_ends_at"])
    assert trial_end == date.today() + timedelta(days=14)

    # Connexion immédiate possible avec le compte tout juste créé
    login = client.post(
        "/api/v1/auth/login", json={"email": "direction@nouvelle-generation.bj", "password": "Str0ng#Passw0rd!"}
    )
    assert login.status_code == 200


def test_signup_duplicate_email_rejected(client):
    payload = {
        "school_name": "École A", "admin_full_name": "X",
        "admin_email": "dup@example.com", "admin_password": "Str0ng#Passw0rd!",
    }
    first = client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/signup", json={**payload, "school_name": "École B"})
    assert second.status_code == 409


def test_signup_weak_password_rejected(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={"school_name": "École C", "admin_full_name": "X", "admin_email": "c@example.com", "admin_password": "123456"},
    )
    assert resp.status_code == 422


def test_signup_similar_school_names_get_distinct_codes(client):
    r1 = client.post(
        "/api/v1/auth/signup",
        json={"school_name": "École Sainte Marie", "admin_full_name": "X", "admin_email": "sm1@example.com", "admin_password": "Str0ng#Passw0rd!"},
    )
    r2 = client.post(
        "/api/v1/auth/signup",
        json={"school_name": "École Sainte Marie", "admin_full_name": "Y", "admin_email": "sm2@example.com", "admin_password": "Str0ng#Passw0rd!"},
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["tenant_id"] != r2.json()["tenant_id"]


# ---------------- Facturation plateforme (Super Admin) ----------------

def test_super_admin_manages_plan_and_invoice_lifecycle(client, make_tenant, make_user, auth_headers):
    super_admin, pwd = make_user(role=UserRole.SUPER_ADMIN)
    headers = auth_headers(super_admin, pwd)

    plan_resp = client.post(
        "/api/v1/platform/plans",
        json={"name": "Pro", "code": "pro-test", "price_per_month": 25000, "max_students": 500},
        headers=headers,
    )
    assert plan_resp.status_code == 201
    plan = plan_resp.json()

    tenant = make_tenant(name="École Facturée")
    sub_resp = client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=headers)
    assert sub_resp.status_code == 201
    assert sub_resp.json()["status"] == "trialing"

    upgrade_resp = client.patch(
        f"/api/v1/platform/tenants/{tenant.id}/subscription",
        json={"plan_id": plan["id"], "status": "active"},
        headers=headers,
    )
    assert upgrade_resp.status_code == 200
    assert upgrade_resp.json()["plan"]["code"] == "pro-test"
    assert upgrade_resp.json()["status"] == "active"

    invoice_resp = client.post(f"/api/v1/platform/tenants/{tenant.id}/invoices/generate", headers=headers)
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()
    assert invoice["amount_due"] == 25000.0
    assert invoice["status"] == "pending"

    # Une deuxième génération pour la même période est refusée (évite le doublon)
    dup_resp = client.post(f"/api/v1/platform/tenants/{tenant.id}/invoices/generate", headers=headers)
    assert dup_resp.status_code == 409

    payment_resp = client.post(
        "/api/v1/platform/payments",
        json={"invoice_id": invoice["id"], "amount": 25000, "method": "mobile_money", "reference": "MOMO-XYZ"},
        headers=headers,
    )
    assert payment_resp.status_code == 201

    invoices_after = client.get(f"/api/v1/platform/tenants/{tenant.id}/invoices", headers=headers).json()
    assert invoices_after[0]["status"] == "paid"
    assert invoices_after[0]["balance"] == 0.0


def test_only_super_admin_manages_platform_billing(client, make_user, make_tenant, auth_headers):
    admin, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    tenant = make_tenant()
    resp = client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=auth_headers(admin, pwd))
    assert resp.status_code == 403


def test_school_admin_can_view_own_subscription_and_invoices(client, make_user, auth_headers):
    admin, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)

    client.post(f"/api/v1/platform/tenants/{admin.tenant_id}/subscription", headers=auth_headers(super_admin, pwd_super))

    resp = client.get("/api/v1/billing/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "trialing"

    invoices_resp = client.get("/api/v1/billing/me/invoices", headers=headers)
    assert invoices_resp.status_code == 200
    assert invoices_resp.json() == []


# ---------------- Suspension et blocage d'accès ----------------

def test_suspended_tenant_is_blocked_from_tenant_scoped_endpoints(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    super_headers = auth_headers(super_admin, pwd_super)
    client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=super_headers)

    # Accès normal pendant l'essai
    assert client.get("/api/v1/students", headers=headers).status_code == 200

    client.patch(f"/api/v1/platform/tenants/{tenant.id}/subscription", json={"status": "suspended"}, headers=super_headers)

    blocked = client.get("/api/v1/students", headers=headers)
    assert blocked.status_code == 402


def test_expired_trial_without_payment_blocks_access(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=auth_headers(super_admin, pwd_super))

    # Simule un essai expiré hier, sans passage à un plan payant
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter_by(tenant_id=tenant.id).one()
        sub.trial_ends_at = date.today() - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/students", headers=headers)
    assert resp.status_code == 402


def test_paying_invoice_reactivates_suspended_subscription(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    super_headers = auth_headers(super_admin, pwd_super)

    client.post(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=super_headers)
    client.patch(f"/api/v1/platform/tenants/{tenant.id}/subscription", json={"status": "suspended"}, headers=super_headers)
    assert client.get("/api/v1/students", headers=auth_headers(admin, pwd)).status_code == 402

    # Le plan d'essai par défaut est gratuit (0 F) : tout paiement, même
    # symbolique, couvre donc le montant dû et doit déclencher la
    # réactivation automatique (total payé >= montant dû).
    invoice = client.post(f"/api/v1/platform/tenants/{tenant.id}/invoices/generate", headers=super_headers).json()
    pay_resp = client.post(
        "/api/v1/platform/payments",
        json={"invoice_id": invoice["id"], "amount": 1, "method": "cash"},
        headers=super_headers,
    )
    assert pay_resp.status_code == 201

    sub_after = client.get(f"/api/v1/platform/tenants/{tenant.id}/subscription", headers=super_headers).json()
    assert sub_after["status"] == "active"
    assert client.get("/api/v1/students", headers=auth_headers(admin, pwd)).status_code == 200


def test_tenant_without_subscription_is_not_restricted(client, make_tenant, make_user, auth_headers):
    """Établissement créé manuellement sans jamais être rattaché à la
    facturation (grandfathering) : aucune restriction d'accès."""
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    resp = client.get("/api/v1/students", headers=auth_headers(admin, pwd))
    assert resp.status_code == 200
