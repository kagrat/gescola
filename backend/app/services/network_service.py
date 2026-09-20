import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.school_network import SchoolNetwork
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.network import NetworkAdminCreate, NetworkCreate


def create_network(db: Session, data: NetworkCreate) -> SchoolNetwork:
    existing = db.execute(select(SchoolNetwork).where(SchoolNetwork.code == data.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce code réseau existe déjà.")
    network = SchoolNetwork(name=data.name, code=data.code)
    db.add(network)
    db.commit()
    db.refresh(network)
    return network


def list_networks(db: Session) -> list[SchoolNetwork]:
    return list(db.execute(select(SchoolNetwork)).scalars().all())


def assign_tenant_to_network(db: Session, *, network_id: uuid.UUID, tenant_id: uuid.UUID) -> Tenant:
    network = db.get(SchoolNetwork, network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Réseau introuvable.")
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    tenant.network_id = network_id
    db.commit()
    db.refresh(tenant)
    return tenant


def create_network_admin(db: Session, *, network_id: uuid.UUID, data: NetworkAdminCreate) -> User:
    network = db.get(SchoolNetwork, network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Réseau introuvable.")

    existing = db.execute(
        select(User).where(User.email == data.email, User.network_id == network_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet e-mail est déjà utilisé pour ce réseau.")

    user = User(
        tenant_id=None, network_id=network_id, email=data.email,
        hashed_password=hash_password(data.password), full_name=data.full_name, role=UserRole.NETWORK_ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
