import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, uuid_pk


class AuditLog(Base):
    """Journal d'audit horodaté (section 7.5 du cahier des charges).

    Volontairement SANS colonne updated_at et sans endpoint de modification :
    une entrée d'audit ne doit jamais pouvoir être altérée après écriture.
    tenant_id est nullable pour couvrir les actions Super Admin transverses.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "grade.override_after_lock"
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "Grade"
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
