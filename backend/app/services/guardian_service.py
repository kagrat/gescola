import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guardian_link import GuardianLink
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.guardian import GuardianLinkCreate
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action


def create_guardian_link(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, data: GuardianLinkCreate
) -> GuardianLink:
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)  # 404 si élève d'un autre tenant

    parent = db.execute(
        select(User).where(User.id == data.parent_user_id, User.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte parent introuvable.")
    if parent.role != UserRole.PARENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce compte n'a pas le rôle Parent — impossible de créer un rattachement.",
        )

    existing = db.execute(
        select(GuardianLink).where(
            GuardianLink.tenant_id == tenant_id,
            GuardianLink.parent_user_id == data.parent_user_id,
            GuardianLink.student_id == data.student_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce rattachement existe déjà.")

    link = GuardianLink(
        tenant_id=tenant_id, parent_user_id=data.parent_user_id, student_id=data.student_id,
        relationship_label=data.relationship_label,
    )
    db.add(link)
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="guardian_link.create",
        target_type="GuardianLink", target_id=None,
        metadata={"parent_user_id": str(data.parent_user_id), "student_id": str(data.student_id)},
    )
    db.commit()
    db.refresh(link)
    return link


def list_children_for_parent(db: Session, *, tenant_id: uuid.UUID, parent_user_id: uuid.UUID) -> list[Student]:
    student_ids = db.execute(
        select(GuardianLink.student_id).where(
            GuardianLink.tenant_id == tenant_id, GuardianLink.parent_user_id == parent_user_id
        )
    ).scalars().all()
    if not student_ids:
        return []
    return list(db.execute(select(Student).where(Student.id.in_(student_ids))).scalars().all())


def list_guardian_links(db: Session, *, tenant_id: uuid.UUID) -> list[GuardianLink]:
    return list(db.execute(select(GuardianLink).where(GuardianLink.tenant_id == tenant_id)).scalars().all())


def delete_guardian_link(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, link_id: uuid.UUID) -> None:
    link = db.execute(
        select(GuardianLink).where(GuardianLink.id == link_id, GuardianLink.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rattachement introuvable.")
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="guardian_link.delete",
        target_type="GuardianLink", target_id=str(link_id),
        metadata={"parent_user_id": str(link.parent_user_id), "student_id": str(link.student_id)},
    )
    db.delete(link)
    db.commit()


def assert_parent_linked_to_student(
    db: Session, *, tenant_id: uuid.UUID, parent_user_id: uuid.UUID, student_id: uuid.UUID
) -> None:
    """Lève 404 (jamais 403 — ne pas confirmer l'existence de l'élève) si aucun
    lien vérifié n'existe entre ce parent et cet élève. À appeler en tout
    premier dans chaque endpoint exposé aux parents."""
    link = db.execute(
        select(GuardianLink).where(
            GuardianLink.tenant_id == tenant_id,
            GuardianLink.parent_user_id == parent_user_id,
            GuardianLink.student_id == student_id,
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Élève introuvable.")
