"""Limite d'élèves du plan d'abonnement (AU-24).

Règles :

* On compte les élèves **actifs** : un élève diplômé, transféré ou archivé
  libère une place (c'est ce qui rend le passage d'année utile au quota).
* Un établissement sans abonnement, ou dont le plan n'a pas de limite
  (`max_students` vide), n'est pas restreint — comme pour l'accès général
  (voir platform_billing_service.check_tenant_access).
* Les opérations qui ajoutent des élèves actifs (création, réactivation,
  import) passent TOUTES par `assert_can_add`, qui prend un verrou par
  établissement : deux inscriptions simultanées ne peuvent pas franchir la
  limite ensemble.
* Réduire le plan sous l'effectif actuel ne retire personne : seules les
  nouvelles inscriptions sont bloquées.
* Refus : 402 (« plan à faire évoluer »), avec les chiffres dans le message.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.billing import Subscription
from app.models.student import Student, StudentStatus


def _limit(db: Session, tenant_id: uuid.UUID) -> tuple[int | None, str | None]:
    sub = db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id)).scalar_one_or_none()
    if sub is None:
        return None, None
    return sub.plan.max_students, sub.plan.name


def _active_count(db: Session, tenant_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(Student).where(
            Student.tenant_id == tenant_id, Student.status == StudentStatus.ACTIVE
        )
    ).scalar_one()


def student_quota(db: Session, *, tenant_id: uuid.UUID) -> dict:
    limit, plan_name = _limit(db, tenant_id)
    active = _active_count(db, tenant_id)
    return {
        "active_students": active, "max_students": limit, "plan_name": plan_name,
        "remaining": None if limit is None else max(0, limit - active),
    }


def assert_can_add(db: Session, *, tenant_id: uuid.UUID, count: int = 1, lock: bool = True) -> None:
    """Refuse (402) si ajouter `count` élèves actifs dépasse la limite du plan.
    Prend le verrou d'établissement jusqu'à la fin de la transaction : l'appelant
    doit donc écrire puis valider (commit) dans la même transaction."""
    if count <= 0:
        return
    if lock:
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"student-quota:{tenant_id}"})
    limit, plan_name = _limit(db, tenant_id)
    if limit is None:
        return
    active = _active_count(db, tenant_id)
    if active + count > limit:
        free = max(0, limit - active)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Limite du plan « {plan_name} » atteinte : {active} élève(s) actif(s) sur {limit} autorisés"
                + (f", il reste {free} place(s) alors que {count} sont demandées." if free else ".")
                + " Passez à un plan supérieur ou libérez des places (élèves diplômés, transférés ou archivés)."
            ),
        )
