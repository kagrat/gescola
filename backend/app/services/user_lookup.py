"""Recherche de comptes par e-mail — comparaison insensible à la casse.

L'e-mail identifie un compte à la connexion (aucun sélecteur d'établissement) :
il est donc unique dans TOUTE la plateforme, garanti par l'index
`uq_users_email_lower` en base. Ces contrôles applicatifs servent à répondre
par un 409 explicite plutôt que par une erreur d'intégrité.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


def email_in_use(db: Session, email: str, *, exclude_user_id: uuid.UUID | None = None) -> bool:
    query = select(User.id).where(func.lower(User.email) == email.strip().lower())
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    return db.execute(query).first() is not None
