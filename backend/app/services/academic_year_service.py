"""Année scolaire : format, année courante d'un établissement, année suivante.

Une seule définition pour toute l'application. L'année courante d'un
établissement est `tenants.academic_year` ; tant qu'elle n'est pas renseignée,
on en déduit une par défaut à partir de la date (septembre → année suivante).
Les notes portent l'année dans laquelle elles ont été saisies : c'est ce qui
permet de passer à l'année suivante sans mélanger les résultats.
"""
import re
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant

YEAR_RE = re.compile(r"^(\d{4})-(\d{4})$")


def default_academic_year(today: date) -> str:
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"


def is_valid_year(value: str) -> bool:
    m = YEAR_RE.match(value or "")
    return bool(m) and int(m.group(2)) == int(m.group(1)) + 1


def next_year(year: str) -> str:
    if not is_valid_year(year):
        raise ValueError(f"Année scolaire invalide : {year!r}")
    start = int(year[:4]) + 1
    return f"{start}-{start + 1}"


def academic_year_of(tenant: Tenant, today: date | None = None) -> str:
    return tenant.academic_year or default_academic_year(today or date.today())


def current_year(db: Session, tenant_id: uuid.UUID) -> str:
    """Année courante d'un établissement (lecture seule)."""
    stored = db.execute(select(Tenant.academic_year).where(Tenant.id == tenant_id)).scalar_one_or_none()
    return stored or default_academic_year(date.today())


def ensure_academic_year(db: Session, tenant_id: uuid.UUID) -> str:
    """Comme current_year, mais FIGE l'année par défaut en base si elle ne l'était pas.

    Sans cela, un établissement n'ayant jamais réglé son année verrait son
    année « courante » basculer toute seule le 1er septembre, et les notes
    déjà saisies disparaîtraient de ses écrans. L'appelant fait le commit."""
    tenant = db.get(Tenant, tenant_id)
    if tenant.academic_year is None:
        tenant.academic_year = default_academic_year(date.today())
        db.flush()
    return tenant.academic_year
