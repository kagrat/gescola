import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_ACT_AS_DIRECTION, CAN_READ_REGISTRY
from app.models.enrollment import StudentEnrollment
from app.schemas.rollover import EnrollmentOut, RolloverProposal, RolloverReport, RolloverRequest
from app.services.academic_service import get_student_or_404
from app.services.rollover_service import DEFAULT_PASS_MARK, build_proposal, run_rollover

router = APIRouter(tags=["academic-year"])


@router.get("/academic-year/proposal", response_model=RolloverProposal)
def rollover_proposal_endpoint(
    pass_mark: float = Query(default=DEFAULT_PASS_MARK, ge=0, le=20),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_ACT_AS_DIRECTION)),
) -> dict:
    """Plan proposé pour la clôture : destination par défaut de chaque classe et
    élèves dont la moyenne annuelle est sous la moyenne de passage. Une simple
    suggestion — la Direction décide."""
    return build_proposal(db, tenant_id=current_user.tenant_id, pass_mark=pass_mark)


@router.post("/academic-year/rollover", response_model=RolloverReport)
def rollover_endpoint(
    payload: RolloverRequest,
    dry_run: bool = Query(default=True, description="true = aperçu sans rien modifier (défaut) ; false = exécution"),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_ACT_AS_DIRECTION)),
) -> RolloverReport:
    return run_rollover(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, req=payload, commit=not dry_run,
    )


@router.get("/students/{student_id}/enrollments", response_model=list[EnrollmentOut])
def student_enrollments_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[EnrollmentOut]:
    get_student_or_404(db, tenant_id=current_user.tenant_id, student_id=student_id)
    rows = db.execute(
        select(StudentEnrollment).where(
            StudentEnrollment.tenant_id == current_user.tenant_id, StudentEnrollment.student_id == student_id
        ).order_by(StudentEnrollment.academic_year.desc())
    ).scalars().all()
    return [
        EnrollmentOut(academic_year=r.academic_year, class_name=r.class_name, outcome=r.outcome.value,
                      next_class_name=r.next_class_name)
        for r in rows
    ]
