"""
Dépendances d'authentification et d'autorisation.
get_current_user  : valide le JWT access token PUIS relit le compte en base :
                     compte actif, version de session à jour (un changement de mot
                     de passe, une désactivation ou une réinitialisation invalide
                     immédiatement les jetons déjà émis), rôle et établissement lus en
                     base — pas dans le jeton — pour qu'une rétrogradation prenne effet
                     tout de suite. Refuse (403) tant que le mot de passe provisoire n'a
                     pas été remplacé.
get_current_user_allow_pending : idem, mais laisse passer un compte qui doit encore
                     changer son mot de passe (uniquement /auth/me et /auth/change-password).
require_roles(...) : factory de dépendance RBAC — restreint un endpoint à une
                     liste de rôles.
get_tenant_db      : fournit une session DB avec le contexte tenant déjà
                     positionné (SET LOCAL app.current_tenant), pour que les
                     policies RLS s'appliquent automatiquement.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import JWTError, TokenType, decode_token
from app.db.session import SessionLocal, set_tenant_context
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)


@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    network_id: uuid.UUID | None
    role: UserRole
    email: str
    must_change_password: bool = False


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les identifiants.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _load_current_user(token: str) -> CurrentUser:
    try:
        payload = decode_token(token)
    except JWTError:
        raise _credentials_exception()
    if payload.get("type") != TokenType.ACCESS.value or not payload.get("sub"):
        raise _credentials_exception()
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise _credentials_exception()

    db = SessionLocal()
    try:
        row = db.execute(
            select(
                User.is_active, User.must_change_password, User.session_version, User.role, User.tenant_id,
                User.network_id, User.email,
            ).where(User.id == user_id)
        ).one_or_none()
    finally:
        db.close()

    # Jeton sans revendication « sv » = émis avant l'introduction des versions de session (valeur 0).
    if row is None or not row.is_active or row.session_version != int(payload.get("sv", 0)):
        raise _credentials_exception()
    return CurrentUser(
        id=user_id, tenant_id=row.tenant_id, network_id=row.network_id, role=row.role, email=row.email,
        must_change_password=row.must_change_password,
    )


def get_current_user_allow_pending(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    return _load_current_user(token)


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    user = _load_current_user(token)
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous devez d'abord choisir un nouveau mot de passe (mot de passe provisoire).",
        )
    return user


def require_roles(*allowed_roles: UserRole):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour cette action.",
            )
        return current_user

    return dependency


def get_tenant_db(current_user: CurrentUser = Depends(get_current_user)):
    """Session DB dont le contexte RLS est déjà positionné pour le tenant de
    l'utilisateur courant. À utiliser dans tous les endpoints scoped-tenant.

    Vérifie aussi que l'abonnement plateforme de l'établissement n'est pas
    suspendu (voir platform_billing_service.check_tenant_access) — un
    établissement sans abonnement suivi n'est pas concerné (grandfathering)."""
    db: Session = SessionLocal()
    try:
        if current_user.tenant_id:
            from app.services.platform_billing_service import check_tenant_access
            check_tenant_access(db, current_user.tenant_id)
        set_tenant_context(db, str(current_user.tenant_id) if current_user.tenant_id else None)
        yield db
    finally:
        db.close()
