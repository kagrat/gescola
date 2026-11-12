"""Recherche paginée des élèves et changement de statut (AU-08, AU-23).

Choix de conception :

* La recherche est *toujours* bornée (limit ≤ MAX_PAGE_SIZE) : aucune requête ne
  peut ramener la table entière d'un établissement d'un coup.
* Le tri est total et stable (nom, prénom, id) : sans ce dernier critère, deux
  élèves homonymes pourraient changer de page d'une requête à l'autre.
* Les caractères joker LIKE (% et _) saisis par l'utilisateur sont échappés :
  chercher « 100% » ne doit pas ramener tout le monde.
* Le changement de statut passe par UNE seule porte, journalisée et motivée.
  La modification générique (PATCH) refuse le champ `status`.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.student import Student, StudentStatus
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action
from app.services.quota_service import assert_can_add

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 100
MAX_SEARCH_TOKENS = 5
MAX_SEARCH_LENGTH = 100


def _escape_like(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_students(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    q: str | None = None,
    class_id: uuid.UUID | None = None,
    unassigned: bool = False,
    student_status: StudentStatus | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[Student], int]:
    """Retourne (élèves de la page, total correspondant aux filtres)."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    conditions = [Student.tenant_id == tenant_id]
    if student_status is not None:
        conditions.append(Student.status == student_status)
    if unassigned:
        conditions.append(Student.class_id.is_(None))
    elif class_id is not None:
        conditions.append(Student.class_id == class_id)

    if q:
        # Chaque mot doit se retrouver dans le prénom, le nom ou le matricule :
        # « jean kakpo » trouve « KAKPO Jean » quel que soit l'ordre saisi.
        for token in q.strip()[:MAX_SEARCH_LENGTH].split()[:MAX_SEARCH_TOKENS]:
            pattern = f"%{_escape_like(token)}%"
            conditions.append(
                or_(
                    Student.first_name.ilike(pattern, escape="\\"),
                    Student.last_name.ilike(pattern, escape="\\"),
                    Student.matricule.ilike(pattern, escape="\\"),
                )
            )

    where = and_(*conditions)
    total = db.execute(select(func.count()).select_from(Student).where(where)).scalar_one()
    rows = db.execute(
        select(Student)
        .where(where)
        .order_by(func.lower(Student.last_name), func.lower(Student.first_name), Student.id)
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    return list(rows), int(total)


def change_student_status(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    student_id: uuid.UUID,
    new_status: StudentStatus,
    reason: str,
) -> Student:
    student = get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Un motif est obligatoire (3 caractères minimum).")
    if student.status == new_status:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="L'élève a déjà ce statut.")

    if new_status == StudentStatus.ACTIVE:
        assert_can_add(db, tenant_id=tenant_id)  # réactiver un élève reprend une place du plan
    old_status = student.status
    student.status = new_status
    # La classe est conservée volontairement : elle documente d'où vient l'élève
    # (historique, bulletins déjà publiés) et permet une réactivation sans
    # perdre l'information. Les listes de classe, les appels et les calculs de
    # moyennes ne retiennent que les élèves « actifs ».
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="student.status_changed",
        target_type="Student", target_id=str(student.id),
        metadata={
            "from": old_status.value, "to": new_status.value, "reason": reason[:500],
            "class_id": str(student.class_id) if student.class_id else None,
        },
    )
    db.commit()
    db.refresh(student)
    return student
