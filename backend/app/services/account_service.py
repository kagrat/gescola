"""Gestion du cycle de vie des comptes.

Règles de hiérarchie (mêmes principes que la création de comptes, voir
user_service.create_user) :
  * le compte Fondateur ne se gère pas depuis l'établissement : ni la Direction
    ni personne d'autre ne peut le modifier, le désactiver ou réinitialiser ses
    accès — seul l'éditeur (Super Admin) le peut, pour dépanner un Fondateur
    bloqué ;
  * un compte Direction ne peut être géré que par le Fondateur ;
  * les autres comptes internes sont gérés par la Direction et le Fondateur ;
  * on ne se désactive pas, ne se réinitialise pas et ne change pas son propre
    rôle (le changement de SON mot de passe passe par change_own_password).

Toute action qui retire ou change des accès invalide immédiatement les
sessions de la personne concernée (version de session + refresh tokens).
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.roles import TENANT_INTERNAL_ROLES
from app.core.security import hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.account import UserUpdate
from app.services.audit_service import log_action
from app.services.auth_service import LOCKOUT_MINUTES, MAX_FAILED_ATTEMPTS, issue_token_pair
from app.services.user_lookup import email_in_use

_PASSWORD_ALPHABETS = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ",  # sans I ni O : se dicte sans ambiguïté
    "abcdefghijkmnpqrstuvwxyz",  # sans l
    "23456789",                  # sans 0 ni 1
    "#@$%&*!?",
)


def generate_temporary_password(length: int = 14) -> str:
    """Mot de passe provisoire fort (au moins une minuscule, une majuscule, un
    chiffre et un caractère spécial), généré avec une source cryptographique."""
    chars = [secrets.choice(alphabet) for alphabet in _PASSWORD_ALPHABETS]
    pool = "".join(_PASSWORD_ALPHABETS)
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def revoke_sessions(db: Session, user: User) -> None:
    """Invalide tout de suite les jetons d'accès (version de session) et
    révoque tous les refresh tokens du compte."""
    user.session_version += 1
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))


# ---------------- Son propre mot de passe ----------------

def change_own_password(db: Session, *, user_id: uuid.UUID, current_password: str, new_password: str) -> tuple[str, str]:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")

    if not verify_password(current_password, user.hashed_password):
        # Même protection anti-force brute que la connexion : sans cela, un jeton volé
        # permettrait de deviner le mot de passe actuel sans limite. 400 (et non 401)
        # pour ne pas déclencher le rafraîchissement automatique du jeton côté client.
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.account_locked",
                       target_type="User", target_id=str(user.id), metadata={"via": "change_password"})
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le mot de passe actuel est incorrect.")

    if verify_password(new_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nouveau mot de passe doit être différent de l'ancien.")

    was_provisional = user.must_change_password
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    revoke_sessions(db, user)  # toutes les autres sessions (et jetons volés) tombent
    log_action(db, tenant_id=user.tenant_id, actor_user_id=user.id, action="auth.password_changed",
               target_type="User", target_id=str(user.id), metadata={"was_provisional": was_provisional})
    db.commit()
    db.refresh(user)
    return issue_token_pair(db, user)  # la session en cours continue avec de nouveaux jetons


# ---------------- Gestion des comptes par un administrateur ----------------

def _get_target(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    target = db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id)).scalar_one_or_none()
    if target is None:
        # 404 (jamais 403) : ne pas confirmer l'existence d'un compte d'un autre établissement.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")
    return target


def _assert_can_manage(actor_id: uuid.UUID, actor_role: UserRole, target: User, *, allow_self: bool = False) -> None:
    if target.id == actor_id and not allow_self:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette action ne peut pas s'appliquer à votre propre compte.")
    if target.role == UserRole.FOUNDER and actor_role != UserRole.SUPER_ADMIN and not (allow_self and target.id == actor_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Le compte Fondateur ne peut pas être géré depuis l'établissement.")
    if target.role == UserRole.SCHOOL_ADMIN and actor_role not in (UserRole.FOUNDER, UserRole.SUPER_ADMIN) \
            and not (allow_self and target.id == actor_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seul le Fondateur peut gérer un compte Direction.")
    if target.role not in TENANT_INTERNAL_ROLES and target.role != UserRole.FOUNDER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce compte ne se gère pas depuis un établissement.")


def update_user(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, user_id: uuid.UUID, data: UserUpdate,
) -> User:
    target = _get_target(db, tenant_id, user_id)
    _assert_can_manage(actor_id, actor_role, target, allow_self=True)
    fields = data.model_fields_set
    changed: list[str] = []

    if "role" in fields and data.role is not None and data.role != target.role:
        if target.id == actor_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas changer votre propre rôle.")
        if data.role == UserRole.FOUNDER or data.role not in TENANT_INTERNAL_ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce rôle ne peut pas être attribué depuis Personnel.")
        if data.role == UserRole.SCHOOL_ADMIN and actor_role != UserRole.FOUNDER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seul le Fondateur peut attribuer le rôle Direction.")
        if (data.role == UserRole.PARENT) != (target.role == UserRole.PARENT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un compte parent ne peut pas devenir un compte du personnel (ni l'inverse) : créez un nouveau compte.",
            )
        target.role = data.role
        revoke_sessions(db, target)  # ses droits changent : les jetons émis avec l'ancien rôle tombent
        changed.append("role")

    if "email" in fields and data.email is not None and data.email.lower() != target.email.lower():
        if email_in_use(db, data.email, exclude_user_id=target.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")
        target.email = data.email
        changed.append("email")

    if "full_name" in fields and data.full_name is not None and data.full_name != target.full_name:
        target.full_name = data.full_name
        changed.append("full_name")

    if changed:
        log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="user.updated", target_type="User",
                   target_id=str(target.id), metadata={"fields": changed})
    db.commit()
    db.refresh(target)
    return target


def set_active(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, user_id: uuid.UUID, active: bool,
) -> User:
    target = _get_target(db, tenant_id, user_id)
    _assert_can_manage(actor_id, actor_role, target)
    if target.is_active == active:
        return target  # déjà dans l'état demandé : rien à faire, rien à journaliser
    target.is_active = active
    if active:
        target.failed_login_attempts = 0
        target.locked_until = None
    else:
        revoke_sessions(db, target)  # perd l'accès immédiatement, sessions en cours comprises
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="user.reactivated" if active else "user.deactivated",
               target_type="User", target_id=str(target.id), metadata={"role": target.role.value})
    db.commit()
    db.refresh(target)
    return target


def reset_password(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, user_id: uuid.UUID,
) -> tuple[User, str]:
    target = _get_target(db, tenant_id, user_id)
    _assert_can_manage(actor_id, actor_role, target)
    temporary = generate_temporary_password()
    target.hashed_password = hash_password(temporary)
    target.must_change_password = True
    target.failed_login_attempts = 0
    target.locked_until = None  # débloque aussi un compte verrouillé après des échecs
    revoke_sessions(db, target)
    # Le mot de passe provisoire n'est JAMAIS écrit dans le journal d'audit.
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="user.password_reset",
               target_type="User", target_id=str(target.id))
    db.commit()
    db.refresh(target)
    return target, temporary


def reset_mfa(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, user_id: uuid.UUID,
) -> User:
    """Désactive la double authentification d'un compte dont la personne a perdu
    son téléphone (sinon elle serait définitivement bloquée). Elle pourra la
    réactiver depuis sa page Sécurité."""
    target = _get_target(db, tenant_id, user_id)
    _assert_can_manage(actor_id, actor_role, target)
    target.mfa_enabled = False
    target.mfa_secret = None
    revoke_sessions(db, target)
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="user.mfa_reset",
               target_type="User", target_id=str(target.id))
    db.commit()
    db.refresh(target)
    return target
