from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, MfaConfirmRequest, MfaDisableRequest, MfaLoginVerifyRequest,
    MfaSetupResponse, RefreshRequest, TokenPair,
)
from app.schemas.signup import SignupRequest, SignupResponse
from app.services.auth_service import authenticate, complete_mfa_login, issue_mfa_pending_token, issue_token_pair, rotate_refresh_token
from app.services.mfa_service import confirm_mfa_setup, disable_mfa, start_mfa_setup
from app.services.signup_service import signup as signup_service

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _get_current_db_user(db: Session, current_user: CurrentUser) -> User:
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    return user


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate(db, email=payload.email, password=payload.password)
    if user.mfa_enabled:
        return LoginResponse(mfa_required=True, mfa_token=issue_mfa_pending_token(user))
    access, refresh = issue_token_pair(db, user)
    return LoginResponse(access_token=access, refresh_token=refresh)


@router.post("/mfa/login-verify", response_model=TokenPair)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def mfa_login_verify(request: Request, payload: MfaLoginVerifyRequest, db: Session = Depends(get_db)) -> TokenPair:
    access, refresh = complete_mfa_login(db, mfa_token=payload.mfa_token, code=payload.code)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    access, refresh_token = rotate_refresh_token(db, payload.refresh_token)
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.post("/signup", response_model=SignupResponse, status_code=201)
@limiter.limit("3/hour")
def signup_endpoint(request: Request, payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    """Inscription en libre-service : crée l'établissement, son compte
    Direction et démarre l'essai gratuit. Limité à 3 inscriptions par heure
    et par adresse IP — un seuil bas assumé pour un endpoint public non
    protégé par CAPTCHA (aucun service de CAPTCHA réel n'est intégré dans ce
    livrable, voir README) : mieux vaut freiner un usage légitime en rafale
    que laisser un script créer des dizaines d'établissements factices."""
    access, refresh_token, tenant, subscription = signup_service(db, payload)
    return SignupResponse(
        access_token=access, refresh_token=refresh_token, tenant_id=str(tenant.id),
        trial_ends_at=subscription.trial_ends_at.isoformat(),
    )


@router.get("/me")
def me(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> dict:
    user = _get_current_db_user(db, current_user)
    return {
        "id": str(current_user.id),
        "tenant_id": str(current_user.tenant_id) if current_user.tenant_id else None,
        "role": current_user.role.value,
        "email": current_user.email,
        "mfa_enabled": user.mfa_enabled,
    }


# --- MFA : gestion de son propre compte (tous rôles) ---

@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> MfaSetupResponse:
    user = _get_current_db_user(db, current_user)
    secret, uri = start_mfa_setup(db, user)
    return MfaSetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/mfa/confirm", status_code=204)
def mfa_confirm(
    payload: MfaConfirmRequest, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> None:
    user = _get_current_db_user(db, current_user)
    confirm_mfa_setup(db, user, payload.code)


@router.post("/mfa/disable", status_code=204)
def mfa_disable(
    payload: MfaDisableRequest, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> None:
    user = _get_current_db_user(db, current_user)
    disable_mfa(db, user, payload.code)
