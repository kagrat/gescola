import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_EXPORT_ATTENDANCE, CAN_MANAGE_ATTENDANCE, CAN_MANAGE_FINANCE, CAN_MANAGE_REGISTRY, CAN_READ_REGISTRY
from app.models.student import StudentStatus
from app.services import export_service as svc

router = APIRouter(prefix="/exports", tags=["exports"])


def _xlsx(content: bytes, name: str) -> Response:
    return Response(content=content, media_type=svc.XLSX, headers={
        "Content-Disposition": f'attachment; filename="{name}-{date.today().isoformat()}.xlsx"', "Cache-Control": "private, no-store"})


@router.get("/students")
def students_export(
    class_id: uuid.UUID | None = None, student_status: StudentStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> Response:
    return _xlsx(svc.export_students(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, class_id=class_id, student_status=student_status), "eleves")


@router.get("/finance")
def finance_export(
    academic_year: str | None = Query(default=None, pattern=r"^\d{4}-\d{4}$"), class_id: uuid.UUID | None = None, state: str | None = None,
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> Response:
    return _xlsx(svc.export_finance(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, academic_year=academic_year, class_id=class_id, state=state), "finances")


@router.get("/attendance")
def attendance_export(
    date_from: date, date_to: date, class_id: uuid.UUID | None = None,
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_EXPORT_ATTENDANCE)),
) -> Response:
    return _xlsx(svc.export_attendance(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, class_id=class_id, date_from=date_from, date_to=date_to), "presences")
