import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, uuid_pk


class SchoolNetwork(Base, TimestampMixin):
    """Un réseau/groupe scolaire : plusieurs établissements (Tenant) rattachés
    à un même promoteur, qui dispose d'une vue consolidée en lecture seule
    sur ses écoles (voir network_reporting_service). Un établissement peut
    exister sans réseau (network_id NULL sur Tenant) — le réseau est une
    fonctionnalité optionnelle, pas une obligation architecturale.
    """

    __tablename__ = "school_networks"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
