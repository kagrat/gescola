import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_GUARDIAN_LINKS
from app.models.user import UserRole
from app.schemas.finance import InvoiceOut
from app.schemas.grade import AttendanceOut, GradeOut, StudentAverageOut
from app.schemas.guardian import ChildOut, GuardianLinkCreate, GuardianLinkOut
from app.services.attendance_service import list_attendance
from app.services.finance_service import list_invoices
from app.services.grade_service import compute_student_average, list_grades
from app.services.guardian_service import (
    assert_parent_linked_to_student, create_guardian_link, delete_guardian_link, list_children_for_parent,
    list_guardian_links,
)

router = APIRouter(tags=["guardian"])


@router.post("/guardian-links", response_model=GuardianLinkOut, status_code=201)
def create_guardian_link_endpoint(
    payload: GuardianLinkCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_GUARDIAN_LINKS)),
) -> GuardianLinkOut:
    return create_guardian_link(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, data=payload)


@router.get("/guardian-links", response_model=list[GuardianLinkOut])
def list_guardian_links_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_GUARDIAN_LINKS)),
) -> list[GuardianLinkOut]:
    return list_guardian_links(db, tenant_id=current_user.tenant_id)


@router.delete("/guardian-links/{link_id}", status_code=204)
def delete_guardian_link_endpoint(
    link_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_GUARDIAN_LINKS)),
) -> None:
    delete_guardian_link(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, link_id=link_id)


@router.get("/me/children", response_model=list[ChildOut])
def list_my_children_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[ChildOut]:
    return list_children_for_parent(db, tenant_id=current_user.tenant_id, parent_user_id=current_user.id)


def _require_own_child(db: Session, current_user: CurrentUser, student_id: uuid.UUID) -> None:
    assert_parent_linked_to_student(
        db, tenant_id=current_user.tenant_id, parent_user_id=current_user.id, student_id=student_id
    )


@router.get("/children/{student_id}/grades", response_model=list[GradeOut])
def child_grades_endpoint(
    student_id: uuid.UUID,
    term: str | None = None,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[GradeOut]:
    _require_own_child(db, current_user, student_id)
    return list_grades(db, tenant_id=current_user.tenant_id, student_id=student_id, term=term)


@router.get("/children/{student_id}/average", response_model=StudentAverageOut)
def child_average_endpoint(
    student_id: uuid.UUID,
    term: str,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> StudentAverageOut:
    _require_own_child(db, current_user, student_id)
    return compute_student_average(db, tenant_id=current_user.tenant_id, student_id=student_id, term=term)


@router.get("/children/{student_id}/attendance", response_model=list[AttendanceOut])
def child_attendance_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[AttendanceOut]:
    _require_own_child(db, current_user, student_id)
    return list_attendance(db, tenant_id=current_user.tenant_id, student_id=student_id)


@router.get("/children/{student_id}/invoices", response_model=list[InvoiceOut])
def child_invoices_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[InvoiceOut]:
    _require_own_child(db, current_user, student_id)
    return list_invoices(db, tenant_id=current_user.tenant_id, student_id=student_id)
