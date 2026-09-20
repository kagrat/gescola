"""
Logique d'authentification.

Politique anti-bruteforce : après MAX_FAILED_ATTEMPTS échecs consécutifs,
le compte est verrouillé pendant LOCKOUT_MINUTES. Ceci s'ajoute (et ne
remplace pas) le rate limiting réseau posé sur l'endpoint /auth/login.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    TokenType,
    create_token,
    hash_refresh_token,
    verify_password,
    verify_totp_code,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.audit_service import log_action

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _generic_auth_error() -> HTTPException:
    # Message volontairement générique : ne jamais révéler si c'est l'email
    # ou le mot de passe qui est incorrect (évite l'énumération de comptes).
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides.")


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None:
        raise _generic_auth_error()

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Compte temporairement verrouillé suite à plusieurs échecs de connexion. Réessayez plus tard.",
        )

    if not user.is_active:
        raise _generic_auth_error()

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            log_action(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="auth.account_locked",
                target_type="User",
                target_id=str(user.id),
                metadata={"failed_attempts": user.failed_login_attempts},
            )
        db.commit()
        raise _generic_auth_error()

    # Connexion réussie : réinitialisation du compteur
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.login_success",
               target_type="User", target_id=str(user.id))
    db.commit()
    return user


def issue_mfa_pending_token(user: User) -> str:
    """Émis juste après validation du mot de passe pour un compte ayant activé
    le MFA — ne permet RIEN d'autre que de compléter la connexion avec un code
    TOTP valide (voir complete_mfa_login). Durée de vie : 5 minutes."""
    tenant_id = str(user.tenant_id) if user.tenant_id else None
    return create_token(
        subject=str(user.id), tenant_id=tenant_id, role=user.role.value, token_type=TokenType.MFA_PENDING,
    )


def complete_mfa_login(db: Session, *, mfa_token: str, code: str) -> tuple[str, str]:
    import uuid as uuid_module

    from app.core.security import JWTError, decode_token

    try:
        payload = decode_token(mfa_token)
    except JWTError:
        raise _generic_auth_error()

    if payload.get("type") != TokenType.MFA_PENDING.value:
        raise _generic_auth_error()

    user = db.get(User, uuid_module.UUID(payload["sub"]))
    if user is None or not user.is_active or not user.mfa_enabled or not user.mfa_secret:
        raise _generic_auth_error()

    if not verify_totp_code(user.mfa_secret, code):
        log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.mfa_code_rejected",
                   target_type="User", target_id=str(user.id))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code de vérification invalide.")

    log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.mfa_login_success",
               target_type="User", target_id=str(user.id))
    db.commit()
    return issue_token_pair(db, user)


def issue_token_pair(db: Session, user: User) -> tuple[str, str]:
    tenant_id = str(user.tenant_id) if user.tenant_id else None
    network_id = str(user.network_id) if user.network_id else None
    access = create_token(
        subject=str(user.id), tenant_id=tenant_id, role=user.role.value,
        token_type=TokenType.ACCESS, extra_claims={"email": user.email, "network_id": network_id},
    )
    refresh_raw = create_token(
        subject=str(user.id), tenant_id=tenant_id, role=user.role.value, token_type=TokenType.REFRESH,
        extra_claims={"network_id": network_id},
    )
    from app.core.security import decode_token  # import local pour éviter un cycle
    payload = decode_token(refresh_raw)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_raw),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return access, refresh_raw


def rotate_refresh_token(db: Session, raw_refresh_token: str) -> tuple[str, str]:
    from app.core.security import JWTError, decode_token

    try:
        payload = decode_token(raw_refresh_token)
    except JWTError:
        raise _generic_auth_error()

    if payload.get("type") != TokenType.REFRESH.value:
        raise _generic_auth_error()

    token_hash = hash_refresh_token(raw_refresh_token)
    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if stored is None or stored.revoked or stored.expires_at < datetime.now(timezone.utc):
        raise _generic_auth_error()

    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise _generic_auth_error()

    # Rotation : l'ancien refresh token est révoqué dès qu'il est utilisé,
    # empêchant le rejeu (detection de vol de token = les deux parties se
    # retrouvent invalidées si un attaquant rejoue un token déjà consommé).
    stored.revoked = True
    db.commit()

    return issue_token_pair(db, user)
