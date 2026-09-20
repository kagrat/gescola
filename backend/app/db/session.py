"""
Gestion des sessions SQLAlchemy et propagation du contexte multi-tenant vers
PostgreSQL pour l'application des policies Row-Level Security (RLS).

Principe de défense en profondeur :
  1. Chaque requête ORM est explicitement filtrée par tenant_id côté
     application (voir app/services/*).
  2. En complément, chaque transaction positionne `app.current_tenant` via
     `SET LOCAL`, variable lue par les policies RLS définies en migration.
     Ainsi, même une requête applicative qui oublierait le filtre tenant_id
     resterait bloquée au niveau base de données.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

NO_TENANT_SENTINEL = "00000000-0000-0000-0000-000000000000"


def set_tenant_context(db: Session, tenant_id: str | None) -> None:
    """Positionne la variable de session Postgres utilisée par les policies RLS.

    tenant_id=None correspond au Super Administrateur (accès multi-tenant) :
    on positionne une valeur sentinelle qu'aucune ligne tenant ne peut jamais
    matcher, et les endpoints Super Admin utilisent des requêtes explicitement
    non filtrées plutôt que de compter sur le contournement RLS.

    Le contexte est mémorisé sur la session (session.info) ET appliqué
    immédiatement : `SET LOCAL` ne vit que le temps de la transaction en
    cours, or un `db.commit()` suivi d'un `db.refresh()` (pattern utilisé
    partout dans les services) ouvre une NOUVELLE transaction implicite.
    L'event listener `_reapply_tenant_context` ci-dessous réapplique donc le
    contexte à chaque nouvelle transaction de la session, pour que toute
    requête ultérieure — y compris après commit — reste protégée par RLS.
    """
    value = tenant_id or NO_TENANT_SENTINEL
    db.info["tenant_context"] = value
    db.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": value})


@event.listens_for(Session, "after_begin")
def _reapply_tenant_context(session: Session, transaction, connection) -> None:
    """Réapplique `SET LOCAL app.current_tenant` à chaque nouvelle transaction
    (y compris celles ouvertes implicitement après un commit) pour les
    sessions ayant un contexte tenant actif."""
    tenant_value = session.info.get("tenant_context")
    if tenant_value:
        connection.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": tenant_value})


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI par défaut (sans contexte tenant — utilisée par les
    endpoints publics comme /auth/login, avant qu'un tenant soit connu)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Utilitaire pour les scripts / tests hors requête HTTP."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
