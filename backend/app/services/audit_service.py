import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Écrit une entrée d'audit. N'effectue PAS de commit — l'appelant décide
    du regroupement transactionnel avec l'action métier concernée."""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
        )
    )
