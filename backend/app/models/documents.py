import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class Certificate(Base, TenantScopedMixin, TimestampMixin):
    """Attestation de scolarité délivrée. Le contenu est FIGÉ à la délivrance
    (`snapshot`) : renommer la classe ou changer l'élève de statut plus tard ne
    réécrit jamais un document déjà remis. Une seule attestation par élève et
    par année : redemander la même renvoie l'originale (même numéro)."""

    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("student_id", "academic_year", name="uq_certificate_student_year"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentVerification(Base):
    """Annuaire PUBLIC des documents vérifiables : code aléatoire → (établissement,
    type, identifiant). Volontairement hors RLS : c'est ce qui permet à un tiers
    (sans compte) de contrôler un document à partir du QR code. Il ne contient
    AUCUNE donnée personnelle ; le détail est lu ensuite dans l'établissement."""

    __tablename__ = "document_verifications"
    __table_args__ = (
        UniqueConstraint("kind", "ref_id", name="uq_document_verification_ref"),
        Index("ix_document_verifications_tenant", "tenant_id"),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "receipt" | "certificate"
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
