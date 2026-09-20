import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Invoice
from app.models.guardian_link import GuardianLink
from app.models.notification import Notification, NotificationType
from app.models.student import Student
from app.services.audit_service import log_action


def create_notification(
    db: Session, *, tenant_id: uuid.UUID, recipient_user_id: uuid.UUID,
    type: NotificationType, title: str, body: str,
) -> Notification:
    notif = Notification(tenant_id=tenant_id, recipient_user_id=recipient_user_id, type=type, title=title, body=body)
    db.add(notif)
    return notif


def list_my_notifications(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Notification]:
    return list(
        db.execute(
            select(Notification)
            .where(Notification.tenant_id == tenant_id, Notification.recipient_user_id == user_id)
            .order_by(Notification.created_at.desc())
        ).scalars().all()
    )


def mark_notification_read(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    notif = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.tenant_id == tenant_id,
            Notification.recipient_user_id == user_id,
        )
    ).scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification introuvable.")
    from datetime import datetime, timezone
    notif.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notif)
    return notif


def send_invoice_reminder(db: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID, actor_id: uuid.UUID) -> int:
    """Envoie une relance in-app à chaque parent rattaché à l'élève concerné
    par la facture. Retourne le nombre de destinataires touchés (0 si aucun
    parent n'est rattaché à cet élève — cas fréquent tant que le portail
    parent n'est pas systématiquement utilisé, à ne pas traiter comme une
    erreur)."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facture introuvable.")

    student = db.get(Student, invoice.student_id)
    guardian_links = db.execute(
        select(GuardianLink).where(GuardianLink.tenant_id == tenant_id, GuardianLink.student_id == invoice.student_id)
    ).scalars().all()

    paid = sum(float(p.amount) for p in invoice.payments)
    balance = float(invoice.amount_due) - paid

    for link in guardian_links:
        create_notification(
            db, tenant_id=tenant_id, recipient_user_id=link.parent_user_id, type=NotificationType.INVOICE_REMINDER,
            title=f"Relance — {invoice.label}",
            body=(
                f"Un solde de {balance:,.0f} F reste dû pour {student.first_name} {student.last_name} "
                f"concernant « {invoice.label} » (échéance {invoice.due_date})."
            ).replace(",", " "),
        )

    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="invoice.reminder_sent",
        target_type="Invoice", target_id=str(invoice_id), metadata={"recipients": len(guardian_links)},
    )
    db.commit()
    return len(guardian_links)
