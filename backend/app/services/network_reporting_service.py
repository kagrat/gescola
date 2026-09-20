import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, set_tenant_context
from app.models.finance import Invoice, InvoiceStatus, Payment
from app.models.school_network import SchoolNetwork
from app.models.student import Student, StudentStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def _school_snapshot(db: Session, tenant: Tenant) -> dict:
    """Lit les indicateurs d'UN établissement, dans son propre contexte RLS.

    Aucune requête ici ne traverse les tenants : on positionne le contexte
    sur CE tenant avant de lire, exactement comme le ferait une session
    school_admin authentifiée sur cet établissement. C'est ce qui permet à un
    promoteur de réseau d'obtenir une vue consolidée sans qu'aucune policy
    RLS n'ait besoin d'être assouplie.
    """
    set_tenant_context(db, str(tenant.id))

    active_students = db.execute(
        select(func.count()).select_from(Student).where(Student.tenant_id == tenant.id, Student.status == StudentStatus.ACTIVE)
    ).scalar_one()

    staff_count = db.execute(
        select(func.count()).select_from(User).where(User.tenant_id == tenant.id, User.role != UserRole.PARENT)
    ).scalar_one()

    amount_due = db.execute(
        select(func.coalesce(func.sum(Invoice.amount_due), 0)).where(
            Invoice.tenant_id == tenant.id, Invoice.status != InvoiceStatus.CANCELLED
        )
    ).scalar_one()
    amount_paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Payment.tenant_id == tenant.id, Invoice.status != InvoiceStatus.CANCELLED)
    ).scalar_one()

    recovery_rate = round(100 * float(amount_paid) / float(amount_due), 1) if amount_due else None

    return {
        "tenant_id": str(tenant.id),
        "name": tenant.name,
        "code": tenant.code,
        "active_students": active_students,
        "staff_count": staff_count,
        "revenue_due": float(amount_due),
        "revenue_collected": float(amount_paid),
        "recovery_rate_percent": recovery_rate,
    }


def network_overview(db: Session, *, network_id: uuid.UUID) -> dict:
    network = db.get(SchoolNetwork, network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Réseau introuvable.")

    tenants = list(db.execute(select(Tenant).where(Tenant.network_id == network_id)).scalars().all())

    # Une session dédiée, distincte de celle utilisée pour lire Tenant/SchoolNetwork
    # (tables non RLS) : on y bascule le contexte tenant établissement par
    # établissement, sans jamais l'ouvrir sur plusieurs tenants à la fois.
    scoped_db = SessionLocal()
    try:
        schools = [_school_snapshot(scoped_db, tenant) for tenant in tenants]
    finally:
        scoped_db.close()

    total_students = sum(s["active_students"] for s in schools)
    total_due = sum(s["revenue_due"] for s in schools)
    total_collected = sum(s["revenue_collected"] for s in schools)
    total_recovery = round(100 * total_collected / total_due, 1) if total_due else None

    return {
        "network": {"id": str(network.id), "name": network.name, "code": network.code},
        "schools": schools,
        "totals": {
            "school_count": len(schools),
            "active_students": total_students,
            "revenue_due": total_due,
            "revenue_collected": total_collected,
            "recovery_rate_percent": total_recovery,
        },
    }
