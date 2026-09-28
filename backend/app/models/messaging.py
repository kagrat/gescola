import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class ThreadKind(str, enum.Enum):
    CONVERSATION = "conversation"   # échange libre
    CONVOCATION = "convocation"     # convocation formelle des parents (date, lieu) — émise par le personnel uniquement


class MessageThread(Base, TenantScopedMixin, TimestampMixin):
    """Fil de discussion entre l'école et les parents, TOUJOURS à propos d'un élève.

    Le rattachement à un élève est ce qui rend l'accès contrôlable : un parent
    ne voit un fil que s'il en est participant ET s'il reste rattaché à l'élève
    (voir messaging_service) ; un enseignant ne peut écrire qu'aux parents
    d'élèves de ses classes. Les participants sont explicites : la Direction ne
    lit pas les fils dont elle n'est pas participante (décision de gouvernance
    à confirmer, voir ROADMAP DP-06)."""

    __tablename__ = "message_threads"

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[ThreadKind] = mapped_column(
        Enum(ThreadKind, name="thread_kind", values_callable=lambda x: [e.value for e in x]),
        default=ThreadKind.CONVERSATION, nullable=False,
    )
    meeting_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meeting_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ThreadParticipant(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "thread_participants"

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL tant que la personne n'a jamais ouvert le fil : sert au compteur de non-lus et à l'accusé « lu ».
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("thread_id", "user_id", name="uq_thread_participant"),)


class Message(Base, TenantScopedMixin, TimestampMixin):
    """Un message n'est jamais modifié ni supprimé : en cas de litige (plainte d'un
    parent, contestation d'une convocation), l'historique fait foi."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class Announcement(Base, TenantScopedMixin, TimestampMixin):
    """Annonce de l'établissement aux familles : à toutes, ou à une classe."""

    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = uuid_pk()
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=True, index=True
    )  # NULL = tout l'établissement
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
