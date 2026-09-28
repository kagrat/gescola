import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_BULLETINS, CAN_MANAGE_COURSEWORK, CAN_READ_BULLETINS, CAN_READ_COURSEWORK
from app.models.user import UserRole
from app.schemas.report_card import (
    AppreciationOut, AppreciationUpsert, GenerateRequest, GenerateResult, RemarksUpdate, ReportCardOut,
    ReportCardSummaryOut,
)
from app.services import bulletin_service as svc

router = APIRouter(tags=["bulletins"])


def _pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.post("/report-cards/generate", response_model=GenerateResult)
def generate_endpoint(
    payload: GenerateRequest, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_BULLETINS)),
) -> GenerateResult:
    return GenerateResult(**svc.generate_report_cards(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, class_id=payload.class_id, term=payload.term,
    ))


@router.get("/report-cards", response_model=list[ReportCardSummaryOut])
def list_endpoint(
    class_id: uuid.UUID | None = None, term: str | None = None, student_id: uuid.UUID | None = None,
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_READ_BULLETINS)),
) -> list[ReportCardSummaryOut]:
    cards = svc.list_report_cards(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role,
        class_id=class_id, term=term, student_id=student_id,
    )
    return [svc.to_summary(c) for c in cards]


@router.get("/report-cards/{card_id}", response_model=ReportCardOut)
def detail_endpoint(
    card_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_BULLETINS)),
) -> ReportCardOut:
    return svc.to_detail(svc.get_report_card(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, card_id=card_id,
    ))


@router.patch("/report-cards/{card_id}", response_model=ReportCardOut)
def remarks_endpoint(
    card_id: uuid.UUID, payload: RemarksUpdate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_BULLETINS)),
) -> ReportCardOut:
    return svc.to_detail(svc.update_remarks(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role,
        card_id=card_id, data=payload,
    ))


@router.post("/report-cards/{card_id}/publish", response_model=ReportCardOut)
def publish_endpoint(
    card_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_BULLETINS)),
) -> ReportCardOut:
    return svc.to_detail(svc.publish_report_card(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, card_id=card_id))


@router.post("/report-cards/{card_id}/unpublish", response_model=ReportCardOut)
def unpublish_endpoint(
    card_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_BULLETINS)),
) -> ReportCardOut:
    return svc.to_detail(svc.unpublish_report_card(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, card_id=card_id))


@router.get("/report-cards/{card_id}/pdf")
def pdf_endpoint(
    card_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_BULLETINS)),
) -> Response:
    card = svc.get_report_card(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, card_id=card_id,
    )
    return _pdf_response(svc.render_report_card_pdf(db, tenant_id=current_user.tenant_id, card=card), f"bulletin-{card.term}.pdf")


# ---------------- Parents ----------------

@router.get("/children/{student_id}/report-cards", response_model=list[ReportCardSummaryOut])
def child_list_endpoint(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> list[ReportCardSummaryOut]:
    cards = svc.list_report_cards_for_child(
        db, tenant_id=current_user.tenant_id, parent_user_id=current_user.id, student_id=student_id,
    )
    return [svc.to_summary(c) for c in cards]


@router.get("/children/{student_id}/report-cards/{card_id}/pdf")
def child_pdf_endpoint(
    student_id: uuid.UUID, card_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.PARENT)),
) -> Response:
    card = svc.get_report_card_for_child(
        db, tenant_id=current_user.tenant_id, parent_user_id=current_user.id, student_id=student_id, card_id=card_id,
    )
    return _pdf_response(svc.render_report_card_pdf(db, tenant_id=current_user.tenant_id, card=card), f"bulletin-{card.term}.pdf")


# ---------------- Appréciations de matière ----------------

@router.put("/appreciations", response_model=AppreciationOut | None)
def upsert_appreciation_endpoint(
    payload: AppreciationUpsert, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_COURSEWORK)),
):
    return svc.upsert_appreciation(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, actor_role=current_user.role, data=payload,
    )


@router.get("/appreciations", response_model=list[AppreciationOut])
def list_appreciations_endpoint(
    class_id: uuid.UUID, subject_id: uuid.UUID, term: str, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_COURSEWORK)),
) -> list[AppreciationOut]:
    return svc.list_appreciations(db, tenant_id=current_user.tenant_id, class_id=class_id, subject_id=subject_id, term=term)
