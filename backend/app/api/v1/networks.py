import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.network import NetworkAdminCreate, NetworkCreate, NetworkOut, NetworkOverviewOut
from app.schemas.user import UserOut
from app.services.network_reporting_service import network_overview
from app.services.network_service import assign_tenant_to_network, create_network, create_network_admin, list_networks

router = APIRouter(tags=["networks"])


@router.post("/networks", response_model=NetworkOut, status_code=201)
def create_network_endpoint(
    payload: NetworkCreate, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> NetworkOut:
    return create_network(db, payload)


@router.get("/networks", response_model=list[NetworkOut])
def list_networks_endpoint(
    db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> list[NetworkOut]:
    return list_networks(db)


@router.post("/networks/{network_id}/tenants/{tenant_id}", status_code=204)
def assign_tenant_endpoint(
    network_id: uuid.UUID, tenant_id: uuid.UUID, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> None:
    assign_tenant_to_network(db, network_id=network_id, tenant_id=tenant_id)


@router.post("/networks/{network_id}/admins", response_model=UserOut, status_code=201)
def create_network_admin_endpoint(
    network_id: uuid.UUID, payload: NetworkAdminCreate, db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> UserOut:
    return create_network_admin(db, network_id=network_id, data=payload)


@router.get("/network/overview", response_model=NetworkOverviewOut)
def network_overview_endpoint(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.NETWORK_ADMIN)),
) -> NetworkOverviewOut:
    # Le promoteur ne consulte que SON réseau (current_user.network_id) —
    # jamais un network_id passé en paramètre, pour ne pas pouvoir deviner
    # l'identifiant d'un autre réseau.
    if current_user.network_id is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun réseau rattaché à ce compte.")
    return network_overview(db, network_id=current_user.network_id)
