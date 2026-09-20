import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, get_current_user
from app.schemas.notification import NotificationOut
from app.services.notification_service import list_my_notifications, mark_notification_read

router = APIRouter(tags=["notifications"])


@router.get("/me/notifications", response_model=list[NotificationOut])
def list_my_notifications_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(get_current_user)
) -> list[NotificationOut]:
    return list_my_notifications(db, tenant_id=current_user.tenant_id, user_id=current_user.id)


@router.post("/me/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read_endpoint(
    notification_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationOut:
    return mark_notification_read(db, tenant_id=current_user.tenant_id, user_id=current_user.id, notification_id=notification_id)
