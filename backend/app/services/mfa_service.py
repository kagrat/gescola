from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generate_mfa_secret, get_totp_provisioning_uri, verify_totp_code
from app.models.user import User
from app.services.audit_service import log_action


def start_mfa_setup(db: Session, user: User) -> tuple[str, str]:
    """Génère un nouveau secret TOTP et le stocke (mfa_enabled reste False tant
    que start_confirm n'a pas validé un premier code — évite qu'un secret
    généré mais jamais confirmé bloque involontairement le compte)."""
    if user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le MFA est déjà activé sur ce compte.")
    secret = generate_mfa_secret()
    user.mfa_secret = secret
    db.commit()
    return secret, get_totp_provisioning_uri(secret, user.email)


def confirm_mfa_setup(db: Session, user: User, code: str) -> None:
    if not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun enrôlement MFA en cours.")
    if not verify_totp_code(user.mfa_secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code de vérification invalide.")
    user.mfa_enabled = True
    log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.mfa_enabled",
               target_type="User", target_id=str(user.id))
    db.commit()


def disable_mfa(db: Session, user: User, code: str) -> None:
    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le MFA n'est pas activé sur ce compte.")
    if not verify_totp_code(user.mfa_secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code de vérification invalide.")
    user.mfa_enabled = False
    user.mfa_secret = None
    log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.mfa_disabled",
               target_type="User", target_id=str(user.id))
    db.commit()
