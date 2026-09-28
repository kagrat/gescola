import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.limiter import limiter
from app.core.roles import (
    CAN_MESSAGE_GUARDIANS, CAN_PUBLISH_ANNOUNCEMENTS, CAN_READ_ANNOUNCEMENTS, CAN_USE_MESSAGING,
)
from app.models.user import User, UserRole
from app.schemas.messaging import (
    AnnouncementCreate, AnnouncementOut, ContactOut, MessageCreate, MessageOut, ThreadCreate, ThreadDetailOut,
    ThreadSummaryOut, UnreadCountOut,
)
from app.services import messaging_service as svc

router = APIRouter(tags=["messaging"])


# ---------------- Fils de discussion ----------------

@router.get("/messages/threads", response_model=list[ThreadSummaryOut])
def list_threads(
    unread: bool = False, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_USE_MESSAGING)),
) -> list[ThreadSummaryOut]:
    return svc.list_threads(db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role, unread_only=unread)


@router.post("/messages/threads", response_model=ThreadDetailOut, status_code=201)
@limiter.limit("60/hour")  # frein anti-spam : un fil = plusieurs destinataires
def create_thread(
    request: Request, payload: ThreadCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_USE_MESSAGING)),
) -> ThreadDetailOut:
    thread_id = svc.create_thread(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, data=payload)
    return svc.get_thread(db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role, thread_id=thread_id)


@router.get("/messages/unread-count", response_model=UnreadCountOut)
def unread_count(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_USE_MESSAGING)),
) -> UnreadCountOut:
    return UnreadCountOut(unread=svc.unread_count(db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role))


@router.get("/messages/guardians", response_model=list[ContactOut])
def guardians_of_student(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MESSAGE_GUARDIANS)),
) -> list[ContactOut]:
    return svc.guardians_for_staff(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, student_id=student_id,
    )


@router.get("/messages/threads/{thread_id}", response_model=ThreadDetailOut)
def get_thread(
    thread_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_USE_MESSAGING)),
) -> ThreadDetailOut:
    return svc.get_thread(db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role, thread_id=thread_id)


@router.post("/messages/threads/{thread_id}/read", status_code=204)
def mark_read(
    thread_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_USE_MESSAGING)),
) -> Response:
    svc.mark_read(db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role, thread_id=thread_id)
    return Response(status_code=204)


@router.post("/messages/threads/{thread_id}/messages", response_model=MessageOut, status_code=201)
@limiter.limit("60/minute")
def send_message(
    request: Request, thread_id: uuid.UUID, payload: MessageCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_USE_MESSAGING)),
) -> MessageOut:
    return svc.send_message(
        db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role, thread_id=thread_id, body=payload.body,
    )


@router.get("/children/{student_id}/contacts", response_model=list[ContactOut])
def contacts_of_child(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[ContactOut]:
    return svc.contacts_for_parent(db, tenant_id=current_user.tenant_id, parent_id=current_user.id, student_id=student_id)


# ---------------- Annonces ----------------

@router.get("/announcements", response_model=list[AnnouncementOut])
def list_announcements(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_READ_ANNOUNCEMENTS)),
) -> list[AnnouncementOut]:
    return svc.list_announcements(db, tenant_id=current_user.tenant_id, user_id=current_user.id, role=current_user.role)


@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    payload: AnnouncementCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_PUBLISH_ANNOUNCEMENTS)),
) -> AnnouncementOut:
    actor = db.get(User, current_user.id)
    return svc.create_announcement(db, tenant_id=current_user.tenant_id, actor=actor, data=payload)


@router.delete("/announcements/{announcement_id}", status_code=204)
def delete_announcement(
    announcement_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_PUBLISH_ANNOUNCEMENTS)),
) -> Response:
    actor = db.get(User, current_user.id)
    svc.delete_announcement(db, tenant_id=current_user.tenant_id, actor=actor, announcement_id=announcement_id)
    return Response(status_code=204)
