"""
Primitives de sécurité.

- Hachage des mots de passe : Argon2id (via passlib), jamais de stockage en clair.
- JWT : access token courte durée + refresh token à rotation, stocké haché en
  base pour permettre la révocation (cf. models/refresh_token.py).

Aucun secret n'est codé en dur : JWT_SECRET_KEY vient de la configuration
(.env / variables d'environnement).
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# Argon2id : résistant aux attaques GPU, recommandé OWASP au-dessus de bcrypt
# pour les nouveaux systèmes. Paramètres par défaut de passlib jugés sûrs ;
# à ajuster (time_cost/memory_cost) selon la capacité du serveur de prod.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    MFA_PENDING = "mfa_pending"  # jeton court, émis après mot de passe validé, avant code TOTP


PASSWORD_COMPLEXITY_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).+$"
)


def validate_password_strength(password: str) -> list[str]:
    """Retourne la liste des règles non respectées (liste vide = mot de passe valide).

    Politique : longueur minimale configurable + au moins une minuscule, une
    majuscule, un chiffre et un caractère spécial. Volontairement pas de
    limite maximale artificielle (on ne tronque jamais un mot de passe).
    """
    errors: list[str] = []
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Le mot de passe doit contenir au moins {settings.PASSWORD_MIN_LENGTH} caractères.")
    if not PASSWORD_COMPLEXITY_RE.match(password):
        errors.append(
            "Le mot de passe doit contenir au moins une minuscule, une majuscule, "
            "un chiffre et un caractère spécial."
        )
    return errors


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Toute erreur de vérification (hash corrompu, etc.) doit être traitée
        # comme un échec d'authentification, jamais lever une exception non
        # gérée qui pourrait fuiter des informations.
        return False


def create_token(
    *,
    subject: str,
    tenant_id: str | None,
    role: str,
    token_type: TokenType,
    extra_claims: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    if token_type == TokenType.ACCESS:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    elif token_type == TokenType.MFA_PENDING:
        expire = now + timedelta(minutes=5)  # fenêtre courte : le temps de saisir le code TOTP
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "type": token_type.value,
        "iat": now,
        "exp": expire,
        "jti": secrets.token_urlsafe(16),  # identifiant unique => révocation possible
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Lève jose.JWTError si le token est invalide, expiré ou mal signé."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def hash_refresh_token(raw_token: str) -> str:
    """Les refresh tokens sont stockés hachés en base (jamais en clair) afin
    qu'une fuite de la base ne permette pas de rejouer les sessions actives."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


# --- Authentification à deux facteurs (TOTP, RFC 6238) ---
# Le secret est un secret partagé standard (base32) compatible avec toute
# application d'authentification (Google Authenticator, Authy, etc.) — aucune
# dépendance à un service tiers, aucune donnée envoyée hors du serveur.

def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="GESCOLA")


def verify_totp_code(secret: str, code: str) -> bool:
    """valid_window=1 tolère un décalage d'horloge de ±30s entre le serveur et
    le téléphone de l'utilisateur, source fréquente de faux rejets sinon."""
    try:
        return pyotp.totp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False


__all__ = [
    "JWTError",
    "TokenType",
    "create_token",
    "decode_token",
    "generate_mfa_secret",
    "get_totp_provisioning_uri",
    "hash_password",
    "hash_refresh_token",
    "validate_password_strength",
    "verify_password",
    "verify_totp_code",
]
