import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, uuid_pk


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"          # multi-établissements, éditeur SaaS
    NETWORK_ADMIN = "network_admin"      # promoteur d'un réseau de plusieurs établissements — vue consolidée en lecture seule
    SCHOOL_ADMIN = "school_admin"        # directeur — établissement unique
    CENSOR = "censor"                    # censeur / surveillant général — discipline, vie scolaire, validation des notes
    SUPERVISOR = "supervisor"            # surveillant — présences et discipline uniquement
    ACCOUNTANT = "accountant"            # comptable — finances uniquement
    STAFF = "staff"                      # secrétariat — inscriptions, administratif général
    TEACHER = "teacher"                  # enseignant
    PARENT = "parent"                    # parent / tuteur — lecture seule, scoped à ses enfants


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    # tenant_id est nullable pour SUPER_ADMIN et NETWORK_ADMIN (portées
    # transverses, non rattachées à un établissement unique). Contrainte
    # applicative vérifiée à la création (voir services/user_service.py et
    # services/network_service.py) plutôt qu'en contrainte SQL, pour garder
    # un message d'erreur explicite côté API.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # network_id n'est renseigné QUE pour le rôle NETWORK_ADMIN.
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_networks.id", ondelete="CASCADE"), nullable=True, index=True
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Authentification à deux facteurs (TOTP) ---
    # mfa_secret n'est jamais exposé via l'API une fois l'enrôlement confirmé ;
    # seul mfa_enabled est lu par le flux de connexion.
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Signature et tampon personnels ---
    # Chaque utilisateur renseigne sa propre signature (et, le cas échéant,
    # son tampon) depuis son propre profil, une fois connecté — jamais rempli
    # ou modifié par un tiers, y compris la Direction. Utilisés pour
    # authentifier les documents qu'il valide (bulletins, attestations).
    # Stockage en base64 directement en base, comme pour Tenant.logo_base64.
    signature_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    stamp_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    __table_args__ = (
        # Un e-mail est unique PAR établissement (deux écoles peuvent avoir
        # chacune un contact@ecole... différent), sauf super_admin (tenant NULL)
        # où l'unicité globale est appliquée en base via un index partiel
        # créé en migration (non exprimable proprement ici avec tenant NULL).
    )
