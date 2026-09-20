import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class NotificationType(str, enum.Enum):
    INVOICE_REMINDER = "invoice_reminder"    # relance de facture impayée
    GRADE_PUBLISHED = "grade_published"      # nouvelle note disponible
    ATTENDANCE_ALERT = "attendance_alert"    # absence non justifiée signalée
    GENERAL = "general"


class Notification(Base, TenantScopedMixin, TimestampMixin):
    """Notification interne à l'application (in-app). Ce livrable n'intègre
    aucune passerelle SMS/e-mail réelle (nécessite un partenariat externe —
    voir README) : ceci est le canal disponible immédiatement, consultable
    dans le portail parent ou par le personnel concerné."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
