import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.billing import Subscription
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.signup import SignupRequest
from app.services.audit_service import log_action
from app.services.auth_service import issue_token_pair
from app.services.platform_billing_service import start_trial_subscription


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "ecole"


def _unique_tenant_code(db: Session, base_name: str) -> str:
    """Génère un code d'établissement unique à partir de son nom. Une
    collision (deux écoles au nom proche) n'est jamais bloquante pour
    l'inscription : on essaie un suffixe numérique croissant plutôt que de
    renvoyer une erreur à quelqu'un qui essaie de créer son compte."""
    base = _slugify(base_name)[:40]
    candidate = base
    suffix = 2
    while db.execute(select(Tenant).where(Tenant.code == candidate)).scalar_one_or_none() is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def signup(db: Session, data: SignupRequest) -> tuple[str, str, Tenant, Subscription]:
    """Crée l'établissement + son compte Direction + l'abonnement d'essai,
    puis renvoie directement une paire de jetons (connexion automatique après
    inscription, pratique standard des SaaS en libre-service)."""
    existing_admin = db.execute(select(User).where(User.email == data.admin_email)).scalar_one_or_none()
    if existing_admin:
        # Message générique : ne pas confirmer qu'un compte existe déjà avec
        # cet e-mail dans un AUTRE établissement (énumération de comptes).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse e-mail est déjà associée à un compte. Connectez-vous ou utilisez une autre adresse.",
        )

    tenant = Tenant(name=data.school_name, code=_unique_tenant_code(db, data.school_name))
    db.add(tenant)
    db.flush()  # obtenir tenant.id sans committer déjà — tout doit réussir ensemble

    admin = User(
        tenant_id=tenant.id, email=data.admin_email, hashed_password=hash_password(data.admin_password),
        full_name=data.admin_full_name, role=UserRole.SCHOOL_ADMIN,
    )
    db.add(admin)
    db.flush()

    subscription = start_trial_subscription(db, tenant_id=tenant.id)

    log_action(
        db, tenant_id=tenant.id, actor_user_id=admin.id, action="tenant.self_signup",
        target_type="Tenant", target_id=str(tenant.id), metadata={"school_name": data.school_name},
    )
    db.commit()
    db.refresh(admin)
    db.refresh(tenant)

    access, refresh = issue_token_pair(db, admin)
    return access, refresh, tenant, subscription
