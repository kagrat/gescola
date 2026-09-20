"""
Dépendances d'authentification et d'autorisation.

get_current_user  : valide le JWT access token, charge l'utilisateur, vérifie
                     qu'il est actif et non verrouillé.
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


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les identifiants.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    try:
        payload = decode_token(token)
    except JWTError:
        raise _credentials_exception()

    if payload.get("type") != TokenType.ACCESS.value:
        raise _credentials_exception()

    user_id = payload.get("sub")
    if not user_id:
        raise _credentials_exception()

    tenant_id = payload.get("tenant_id")
    network_id = payload.get("network_id")
    return CurrentUser(
        id=uuid.UUID(user_id),
        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
        network_id=uuid.UUID(network_id) if network_id else None,
        role=UserRole(payload["role"]),
        email=payload.get("email", ""),
    )


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
