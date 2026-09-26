from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_ACT_AS_DIRECTION
from app.schemas.audit import AuditLogOut
from app.services.audit_query_service import list_audit_logs

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_ACT_AS_DIRECTION)),
) -> list[AuditLogOut]:
    return list_audit_logs(db, tenant_id=current_user.tenant_id)
