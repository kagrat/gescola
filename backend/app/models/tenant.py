import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, uuid_pk


class Tenant(Base, TimestampMixin):
    """Un établissement scolaire. Racine de l'isolation multi-tenant.

    network_id (optionnel) rattache cet établissement à un SchoolNetwork —
    un promoteur possédant plusieurs écoles peut ainsi obtenir une vue
    consolidée (voir UserRole.NETWORK_ADMIN) sans que cela n'affaiblisse
    l'isolation RLS entre établissements : le rattachement ne donne AUCUN
    accès direct aux données d'un établissement, seulement à des agrégats
    lus établissement par établissement (voir network_reporting_service).

    Les champs d'identité légale (trade_name, rccm, ifu, address, logo) sont
    facultatifs et modifiables uniquement par la Direction de l'établissement
    (voir establishment_service) — utiles pour l'en-tête des documents
    officiels générés (bulletins, attestations). logo_base64 stocke l'image
    encodée en base64 directement en base : aucun service de stockage de
    fichiers externe (S3, Cloudinary...) n'est intégré dans ce livrable.
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # slug/identifiant court
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_networks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Identité légale / administrative (facultatif) ---
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rccm: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ifu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    logo_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
