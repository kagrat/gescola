import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantScopedMixin, TimestampMixin, uuid_pk


class GuardianLink(Base, TenantScopedMixin, TimestampMixin):
    """Rattachement vérifié entre un compte utilisateur de rôle PARENT et un
    élève. C'est la SEULE source de vérité pour l'accès parent — sans entrée
    ici, un compte PARENT n'a accès à rien (voir guardian_service).

    Créé exclusivement par la direction ou le secrétariat (acte administratif,
    jamais en libre-service par le parent lui-même), pour éviter qu'un compte
    parent puisse se rattacher à n'importe quel élève.
    """

    __tablename__ = "guardian_links"

    id: Mapped[uuid.UUID] = uuid_pk()
    parent_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_label: Mapped[str] = mapped_column(String(50), nullable=False)  # ex: "Mère", "Père", "Tuteur légal"

    __table_args__ = (
        UniqueConstraint("parent_user_id", "student_id", name="uq_guardian_link_parent_student"),
    )
