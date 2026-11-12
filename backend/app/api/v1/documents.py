import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.limiter import limiter
from app.core.roles import CAN_ACT_AS_DIRECTION, CAN_MANAGE_FINANCE, CAN_MANAGE_REGISTRY
from app.db.session import get_db
from app.schemas.finance import CertificateOut, CertificateVoid, PublicVerification, StudentPaymentRow
from app.services import document_service as svc

router = APIRouter(tags=["documents"])


def pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"})


@router.get("/students/{student_id}/payments", response_model=list[StudentPaymentRow])
def student_payments_endpoint(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> list[dict]:
    return svc.list_student_payments(db, tenant_id=current_user.tenant_id, student_id=student_id)


@router.get("/payments/{payment_id}/receipt")
def receipt_endpoint(
    payment_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_FINANCE)),
) -> Response:
    pdf, number = svc.render_receipt(db, tenant_id=current_user.tenant_id, payment_id=payment_id)
    return pdf_response(pdf, f"recu-{number:06d}.pdf")


@router.post("/students/{student_id}/certificate", response_model=CertificateOut, status_code=201)
def issue_certificate_endpoint(
    student_id: uuid.UUID, response: Response, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
):
    cert, created = svc.issue_certificate(db, tenant_id=current_user.tenant_id, student_id=student_id, actor_id=current_user.id)
    if not created:
        response.status_code = 200  # déjà délivrée cette année : on renvoie l'originale
    return cert


@router.get("/students/{student_id}/certificates", response_model=list[CertificateOut])
def list_certificates_endpoint(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
):
    return svc.list_certificates(db, tenant_id=current_user.tenant_id, student_id=student_id)


@router.get("/certificates/{certificate_id}/pdf")
def certificate_pdf_endpoint(
    certificate_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> Response:
    pdf, number = svc.render_certificate(db, tenant_id=current_user.tenant_id, certificate_id=certificate_id)
    return pdf_response(pdf, f"attestation-{number:06d}.pdf")


@router.post("/certificates/{certificate_id}/void", response_model=CertificateOut)
def void_certificate_endpoint(
    certificate_id: uuid.UUID, payload: CertificateVoid, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_ACT_AS_DIRECTION)),
):
    return svc.void_certificate(db, tenant_id=current_user.tenant_id, certificate_id=certificate_id, actor_id=current_user.id, reason=payload.reason)


# ---- Public : aucune authentification (contrôle d'un document à partir de son QR code) ----

@router.get("/public/verify/{code}", response_model=PublicVerification)
@limiter.shared_limit(get_settings().PUBLIC_VERIFY_RATE_LIMIT, scope="public-verify")  # un seul compteur, quel que soit le code essayé
def public_verify_endpoint(request: Request, code: str, db: Session = Depends(get_db)):
    return svc.verify_public(db, code)
