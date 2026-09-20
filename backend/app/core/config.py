"""
Configuration centrale de l'application.

Toutes les valeurs sensibles (secrets JWT, mot de passe DB) sont lues depuis
l'environnement (.env en local, variables d'environnement réelles en prod).
Rien n'est jamais codé en dur ici : voir .env.example pour la liste des
variables requises.
"""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "GESCOLA API"
    ENVIRONMENT: str = Field(default="development")  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"

    # --- Base de données ---
    # Railway (et d'autres PaaS) injectent DATABASE_URL au format
    # "postgresql://..." ou "postgres://..." sans préciser le driver —
    # normalisé automatiquement vers "postgresql+psycopg2://" ci-dessous
    # (validator) pour éviter d'avoir à réécrire la variable à la main.
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://gescola_app:gescola_dev_change_me@localhost:5432/gescola_dev"
    )

    # --- Sécurité JWT ---
    # Obligatoire en production : aucune valeur par défaut utilisable en clair.
    JWT_SECRET_KEY: str = Field(default="CHANGE_ME_INSECURE_DEV_ONLY_DO_NOT_USE_IN_PROD")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Politique de mot de passe ---
    PASSWORD_MIN_LENGTH: int = 10

    # --- CORS ---
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Rate limiting ---
    LOGIN_RATE_LIMIT: str = "5/minute"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def secret_must_be_overridden_in_prod(cls, v: str, info) -> str:
        # La validation stricte (refus de démarrer) est faite dans main.py au
        # démarrage plutôt qu'ici, car ENVIRONMENT n'est pas encore disponible
        # de façon fiable à ce stade de la validation champ par champ.
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Accepte les URL fournies telles quelles par les PaaS (Railway,
        Render, Heroku...) — "postgres://" (ancien alias) ou "postgresql://"
        sans driver explicite — et les convertit vers le format attendu par
        SQLAlchemy + psycopg2. N'affecte pas une URL déjà correctement formée."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg2://" + v[len("postgresql://"):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
