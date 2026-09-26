from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.user import TenantCreate
from app.services.audit_service import log_action
from app.services.platform_billing_service import start_trial_subscription


def create_tenant(db: Session, data: TenantCreate) -> Tenant:
    """Crée l'établissement ET son premier compte — un compte FONDATEUR, pas
    Direction : c'est cohérent avec le flux réel (« Super Admin → crée
    l'établissement + le compte Fondateur → le Fondateur configure
    l'établissement et crée le personnel, dont la Direction »). Un essai
    gratuit démarre automatiquement, exactement comme pour l'inscription en
    libre-service (voir signup_service.signup)."""
    existing_tenant = db.execute(select(Tenant).where(Tenant.code == data.code)).scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce code établissement existe déjà.")

    existing_admin = db.execute(select(User).where(User.email == data.admin_email)).scalar_one_or_none()
    if existing_admin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette adresse e-mail est déjà utilisée.")

    tenant = Tenant(name=data.name, code=data.code)
    db.add(tenant)
    db.flush()

    founder = User(
        tenant_id=tenant.id, email=data.admin_email, hashed_password=hash_password(data.admin_password),
        full_name=data.admin_full_name, role=UserRole.FOUNDER,
    )
    db.add(founder)
    db.flush()

    start_trial_subscription(db, tenant_id=tenant.id)

    log_action(
        db, tenant_id=tenant.id, actor_user_id=None, action="tenant.created_by_super_admin",
        target_type="Tenant", target_id=str(tenant.id), metadata={"founder_email": data.admin_email},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


def list_tenants(db: Session) -> list[Tenant]:
    return list(db.execute(select(Tenant)).scalars().all())
