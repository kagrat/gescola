import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_LOCK_GRADES, CAN_OVERRIDE_LOCKED_GRADES, CAN_READ_GRADES, CAN_WRITE_GRADES
from app.schemas.grade import GradeCreate, GradeOut, StudentAverageOut
from app.services.grade_service import compute_student_average, create_grade, lock_term_grades, list_grades, update_grade

router = APIRouter(tags=["grades"])


class GradeUpdate(BaseModel):
    value: float

    @field_validator("value")
    @classmethod
    def value_range(cls, v: float) -> float:
        if not (0 <= v <= 20):
            raise ValueError("La note doit être comprise entre 0 et 20.")
        return v


@router.post("/grades", response_model=GradeOut, status_code=201)
def create_grade_endpoint(
    payload: GradeCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_WRITE_GRADES)),
) -> GradeOut:
    return create_grade(db, tenant_id=current_user.tenant_id, teacher_id=current_user.id, actor_role=current_user.role, data=payload)


@router.get("/students/{student_id}/grades", response_model=list[GradeOut])
def list_grades_endpoint(
    student_id: uuid.UUID,
    term: str | None = None,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_GRADES)),
) -> list[GradeOut]:
    return list_grades(db, tenant_id=current_user.tenant_id, student_id=student_id, term=term)


@router.get("/students/{student_id}/average", response_model=StudentAverageOut)
def student_average_endpoint(
    student_id: uuid.UUID,
    term: str,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_GRADES)),
) -> StudentAverageOut:
    return compute_student_average(db, tenant_id=current_user.tenant_id, student_id=student_id, term=term)


@router.post("/students/{student_id}/grades/lock")
def lock_grades_endpoint(
    student_id: uuid.UUID,
    term: str,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_LOCK_GRADES)),
) -> dict:
    count = lock_term_grades(db, tenant_id=current_user.tenant_id, student_id=student_id, term=term, actor_id=current_user.id)
    return {"locked_count": count}


@router.patch("/grades/{grade_id}", response_model=GradeOut)
def update_grade_endpoint(
    grade_id: uuid.UUID,
    payload: GradeUpdate,
    db: Session = Depends(get_tenant_db),
    # TEACHER peut modifier ses propres notes tant qu'elles ne sont pas verrouillées ;
    # CENSOR/SCHOOL_ADMIN peuvent en plus déverrouiller exceptionnellement (tracé).
    current_user: CurrentUser = Depends(require_roles(*set(CAN_WRITE_GRADES) | set(CAN_OVERRIDE_LOCKED_GRADES))),
) -> GradeOut:
    is_admin_override = current_user.role in CAN_OVERRIDE_LOCKED_GRADES
    return update_grade(
        db, tenant_id=current_user.tenant_id, grade_id=grade_id, actor_id=current_user.id,
        is_admin_override=is_admin_override, new_value=payload.value,
    )
