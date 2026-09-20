"""
Fixtures partagées.

Les tests tournent contre une VRAIE base PostgreSQL (gescola_test), pas contre
SQLite : les policies Row-Level Security testées en test_tenant_isolation.py
sont spécifiques à PostgreSQL et n'existent pas sous SQLite. C'est
volontaire — un test d'isolation multi-tenant qui ne passerait pas par le
vrai moteur RLS ne prouverait rien.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg2://gescola_app:gescola_dev_change_me@localhost:5432/gescola_test"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("ENVIRONMENT", "test")
# Le rate limit de production (5/minute) est volontairement strict pour un
# endpoint d'authentification. Certains tests (verrouillage de compte après
# 5 échecs + une 6e requête pour vérifier le blocage) ont besoin d'un quota
# plus large pour tester le comportement applicatif indépendamment du rate
# limiting réseau — les deux mécanismes sont testés séparément.
os.environ.setdefault("LOGIN_RATE_LIMIT", "1000/minute")

from app.core.security import hash_password  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.session import SessionLocal, set_tenant_context  # noqa: E402
from app.main import app  # noqa: E402
from app.models.school_network import SchoolNetwork  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Le rate limiter est un état global en mémoire du processus ; sans reset,
    les tests suivants hériteraient du quota consommé par les précédents,
    ce qui n'a rien à voir avec le comportement testé ici."""
    limiter.reset()
    yield

TABLES_TO_CLEAN = [
    "platform_payments", "platform_invoices", "subscriptions", "platform_plans",
    "loans", "books", "canteen_subscriptions", "canteen_plans",
    "notifications", "guardian_links", "payments", "invoices", "attendances", "grades", "audit_logs",
    "refresh_tokens", "students", "subjects", "school_classes", "users", "tenants", "school_networks",
]


@pytest.fixture(autouse=True)
def clean_db():
    """Vide toutes les tables avant chaque test pour garantir l'isolation des
    scénarios (les tests ne doivent jamais dépendre de l'ordre d'exécution).

    platform_plans est réensemencé avec le plan d'essai gratuit par défaut
    juste après troncature (exactement comme le fait la migration en
    production) : plusieurs services (signup, démarrage d'abonnement)
    en dépendent, et le tronquer sans le recréer casserait tous les tests
    qui en découlent — l'accumulation de plans de test d'un lancement à
    l'autre était elle-même un bug d'isolation, corrigé ici."""
    db = SessionLocal()
    try:
        # TRUNCATE ... CASCADE gère l'ordre des clés étrangères sans nécessiter
        # de privilège superuser (contrairement à session_replication_role,
        # réservé au rôle propriétaire de la base en environnement managé).
        db.execute(text("TRUNCATE TABLE " + ", ".join(TABLES_TO_CLEAN) + " CASCADE"))
        db.execute(
            text(
                "INSERT INTO platform_plans (id, name, code, price_per_month, max_students, "
                "is_default_trial_plan, is_active, created_at, updated_at) "
                "VALUES (gen_random_uuid(), 'Essai gratuit', 'essai-gratuit', 0, 100, true, true, now(), now())"
            )
        )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_tenant():
    def _make(name: str = "École Test", code: str | None = None) -> Tenant:
        db = SessionLocal()
        try:
            tenant = Tenant(name=name, code=code or f"tenant-{uuid.uuid4().hex[:8]}")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            return tenant
        finally:
            db.close()

    return _make


@pytest.fixture
def make_network():
    def _make(name: str = "Réseau Test", code: str | None = None) -> SchoolNetwork:
        db = SessionLocal()
        try:
            network = SchoolNetwork(name=name, code=code or f"network-{uuid.uuid4().hex[:8]}")
            db.add(network)
            db.commit()
            db.refresh(network)
            return network
        finally:
            db.close()

    return _make


@pytest.fixture
def make_user(make_tenant):
    def _make(
        *, tenant=None, network=None, role: UserRole = UserRole.SCHOOL_ADMIN, email: str | None = None,
        password: str = "CorrectHorse#123",
    ) -> tuple[User, str]:
        if role not in (UserRole.SUPER_ADMIN, UserRole.NETWORK_ADMIN) and tenant is None:
            tenant = make_tenant()
        db = SessionLocal()
        try:
            user = User(
                tenant_id=tenant.id if tenant else None,
                network_id=network.id if network else None,
                email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
                hashed_password=hash_password(password),
                full_name="Utilisateur Test",
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user, password
        finally:
            db.close()

    return _make


@pytest.fixture
def auth_headers(client, make_user):
    """Retourne une factory qui connecte un utilisateur et fournit ses headers."""

    def _login(user: User, password: str) -> dict:
        resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login


@pytest.fixture
def tenant_db_session():
    """Session DB avec contexte RLS positionné manuellement — pour les tests
    bas niveau qui veulent vérifier le comportement de la base directement."""

    def _session(tenant_id: uuid.UUID | None):
        db = SessionLocal()
        set_tenant_context(db, str(tenant_id) if tenant_id else None)
        return db

    return _session
