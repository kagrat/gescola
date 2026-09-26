import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import TENANT_INTERNAL_ROLES
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


def create_user(db: Session, *, tenant_id: uuid.UUID | None, actor_role: UserRole, data: UserCreate) -> User:
    if data.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte Super Administrateur ne peut pas être créé depuis un établissement.",
        )
    if data.role == UserRole.FOUNDER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le compte Fondateur ne peut être créé qu'à la création de l'établissement, pas depuis Personnel.",
        )
    if data.role == UserRole.SCHOOL_ADMIN and actor_role != UserRole.FOUNDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le Fondateur peut créer un compte Direction.",
        )
    if data.role not in TENANT_INTERNAL_ROLES or tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un établissement est obligatoire pour ce rôle.",
        )

    existing = db.execute(
        select(User).where(User.email == data.email, User.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé.")

    user = User(
        tenant_id=tenant_id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, *, tenant_id: uuid.UUID) -> list[User]:
    return list(db.execute(select(User).where(User.tenant_id == tenant_id)).scalars().all())
