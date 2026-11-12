"""Reçus de paiement, attestations de scolarité et vérification publique (AU-10).

Principes :
  * numérotation continue par établissement, par `UPDATE ... RETURNING` sur le
    compteur de l'établissement (verrou de ligne : aucun doublon en concurrence) ;
  * chaque document a un code aléatoire (96 bits) dans l'annuaire public
    `document_verifications` (hors RLS, sans donnée personnelle) ;
  * une attestation est figée à la délivrance, et peut être ANNULÉE (jamais
    supprimée) : la vérification publique l'affiche alors comme annulée ;
  * la vérification publique ne renvoie que le strict nécessaire pour
    comparer avec le papier.
"""
import secrets
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import set_tenant_context
from app.models.academic import SchoolClass
from app.models.documents import Certificate, DocumentVerification
from app.models.finance import Invoice, Payment
from app.models.student import Student, StudentStatus
from app.models.tenant import Tenant
from app.services.academic_year_service import ensure_academic_year
from app.services.audit_service import log_action
from app.services.document_pdf import build_certificate_pdf, build_receipt_pdf

RECEIPT, CERTIFICATE = "receipt", "certificate"


def next_number(db: Session, tenant_id: uuid.UUID, counter: str) -> int:
    if counter not in ("receipt_counter", "certificate_counter"):
        raise ValueError(counter)
    return db.execute(
        text(f"UPDATE tenants SET {counter} = {counter} + 1 WHERE id = :t RETURNING {counter}"), {"t": tenant_id}
    ).scalar_one()


def register_verification(db: Session, *, tenant_id: uuid.UUID, kind: str, ref_id: uuid.UUID) -> str:
    code = secrets.token_urlsafe(12)
    db.add(DocumentVerification(code=code, tenant_id=tenant_id, kind=kind, ref_id=ref_id))
    db.flush()
    return code


def verification_code(db: Session, *, kind: str, ref_id: uuid.UUID) -> str:
    code = db.execute(
        select(DocumentVerification.code).where(DocumentVerification.kind == kind, DocumentVerification.ref_id == ref_id)
    ).scalar_one_or_none()
    if code is None:  # ne doit pas arriver (créé avec le document) ; on répare plutôt que d'échouer
        raise HTTPException(status_code=500, detail="Code de vérification manquant.")
    return code


def verify_url(code: str) -> str:
    return f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/verifier/{code}"


def _render_settings(tenant: Tenant) -> tuple[dict, dict]:
    return (
        {"name": tenant.name, "trade_name": tenant.trade_name, "address": tenant.address, "rccm": tenant.rccm, "ifu": tenant.ifu,
         "motto": tenant.bulletin_motto, "authority_header": tenant.bulletin_authority_header, "place": tenant.bulletin_place},
        {"logo": tenant.logo_base64},
    )


def _student_name(s: Student) -> str:
    return f"{s.last_name.upper()} {s.first_name}"


# ---------------- Reçus ----------------

def _payment_or_404(db: Session, tenant_id: uuid.UUID, payment_id: uuid.UUID) -> tuple[Payment, Invoice, Student]:
    row = db.execute(
        select(Payment, Invoice, Student)
        .join(Invoice, Payment.invoice_id == Invoice.id).join(Student, Invoice.student_id == Student.id)
        .where(Payment.id == payment_id, Payment.tenant_id == tenant_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paiement introuvable.")
    return row


def receipt_data(db: Session, tenant_id: uuid.UUID, payment: Payment, invoice: Invoice, student: Student) -> dict:
    # Solde APRÈS ce paiement = dû − paiements saisis jusqu'à celui-ci (et non le solde d'aujourd'hui).
    paid_until = db.execute(
        select(Payment.amount).where(
            Payment.invoice_id == invoice.id, Payment.tenant_id == tenant_id,
            (Payment.receipt_number <= payment.receipt_number),
        )
    ).scalars().all()
    class_name = db.execute(select(SchoolClass.name).where(SchoolClass.id == student.class_id)).scalar_one_or_none() if student.class_id else None
    return {
        "number": payment.receipt_number, "student_name": _student_name(student), "class_name": class_name,
        "invoice_label": invoice.label, "academic_year": invoice.academic_year, "amount": float(payment.amount),
        "method": payment.method.value, "reference": payment.reference, "paid_on": payment.created_at.date().isoformat(),
        "total_due": float(invoice.amount_due), "balance_after": round(float(invoice.amount_due) - sum(float(a) for a in paid_until), 2),
    }


def render_receipt(db: Session, *, tenant_id: uuid.UUID, payment_id: uuid.UUID, student_id: uuid.UUID | None = None) -> tuple[bytes, int]:
    payment, invoice, student = _payment_or_404(db, tenant_id, payment_id)
    if student_id is not None and student.id != student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paiement introuvable.")
    tenant = db.get(Tenant, tenant_id)
    settings, images = _render_settings(tenant)
    code = verification_code(db, kind=RECEIPT, ref_id=payment.id)
    pdf = build_receipt_pdf(
        settings=settings, images=images, data=receipt_data(db, tenant_id, payment, invoice, student), code=code,
        verify_url=verify_url(code), issued_on=payment.created_at.date(),
    )
    return pdf, payment.receipt_number


def list_student_payments(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Payment, Invoice).join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.student_id == student_id, Payment.tenant_id == tenant_id)
        .order_by(Payment.receipt_number.desc())
    ).all()
    return [{
        "id": p.id, "invoice_id": i.id, "invoice_label": i.label, "amount": float(p.amount), "method": p.method,
        "reference": p.reference, "receipt_number": p.receipt_number, "paid_on": p.created_at.date(),
    } for p, i in rows]


# ---------------- Attestations ----------------

def _student_or_404(db: Session, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    s = db.execute(select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Élève introuvable.")
    return s


def issue_certificate(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID, actor_id: uuid.UUID) -> tuple[Certificate, bool]:
    """Délivre (ou renvoie, si elle existe déjà) l'attestation de l'année courante. Retourne (attestation, créée?)."""
    student = _student_or_404(db, tenant_id, student_id)
    if student.status != StudentStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seul un élève actif peut recevoir une attestation de scolarité.")
    if student.class_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Affectez d'abord l'élève à une classe.")
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"certificate:{student_id}"})
    year = ensure_academic_year(db, tenant_id)
    existing = db.execute(
        select(Certificate).where(Certificate.student_id == student_id, Certificate.academic_year == year)
    ).scalar_one_or_none()
    if existing is not None:
        db.commit()
        return existing, False
    class_name = db.execute(select(SchoolClass.name).where(SchoolClass.id == student.class_id)).scalar_one()
    cert = Certificate(
        tenant_id=tenant_id, student_id=student_id, academic_year=year, number=next_number(db, tenant_id, "certificate_counter"),
        issued_by=actor_id,
        snapshot={"student_name": _student_name(student), "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
                  "matricule": student.matricule, "class_name": class_name, "academic_year": year},
    )
    db.add(cert)
    db.flush()
    register_verification(db, tenant_id=tenant_id, kind=CERTIFICATE, ref_id=cert.id)
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="certificate.issued", target_type="Student",
               target_id=str(student_id), metadata={"number": cert.number, "academic_year": year})
    db.commit()
    db.refresh(cert)
    return cert, True


def list_certificates(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[Certificate]:
    _student_or_404(db, tenant_id, student_id)
    return list(db.execute(
        select(Certificate).where(Certificate.tenant_id == tenant_id, Certificate.student_id == student_id)
        .order_by(Certificate.academic_year.desc())
    ).scalars())


def _certificate_or_404(db: Session, tenant_id: uuid.UUID, certificate_id: uuid.UUID) -> Certificate:
    c = db.execute(select(Certificate).where(Certificate.id == certificate_id, Certificate.tenant_id == tenant_id)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attestation introuvable.")
    return c


def render_certificate(db: Session, *, tenant_id: uuid.UUID, certificate_id: uuid.UUID, student_id: uuid.UUID | None = None) -> tuple[bytes, int]:
    cert = _certificate_or_404(db, tenant_id, certificate_id)
    if student_id is not None and cert.student_id != student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attestation introuvable.")
    settings, images = _render_settings(db.get(Tenant, tenant_id))
    code = verification_code(db, kind=CERTIFICATE, ref_id=cert.id)
    pdf = build_certificate_pdf(
        settings=settings, images=images, snapshot=cert.snapshot, number=cert.number, code=code, verify_url=verify_url(code),
        issued_on=cert.created_at.date(), voided=cert.voided_at is not None,
    )
    return pdf, cert.number


def void_certificate(db: Session, *, tenant_id: uuid.UUID, certificate_id: uuid.UUID, actor_id: uuid.UUID, reason: str) -> Certificate:
    cert = _certificate_or_404(db, tenant_id, certificate_id)
    if cert.voided_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette attestation est déjà annulée.")
    cert.voided_at = datetime.now(timezone.utc)
    cert.void_reason = reason.strip()
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="certificate.voided", target_type="Student",
               target_id=str(cert.student_id), metadata={"number": cert.number, "reason": cert.void_reason})
    db.commit()
    db.refresh(cert)
    return cert


# ---------------- Vérification publique ----------------

def verify_public(db: Session, code: str) -> dict:
    """Aucune authentification : lit l'annuaire public, bascule sur l'établissement, renvoie le minimum.
    Un code inconnu et un document introuvable donnent la MÊME réponse (404)."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    if not code or len(code) > 32:
        raise not_found
    entry = db.get(DocumentVerification, code)
    if entry is None:
        raise not_found
    set_tenant_context(db, str(entry.tenant_id))
    tenant = db.get(Tenant, entry.tenant_id)
    school = tenant.trade_name or tenant.name
    if entry.kind == RECEIPT:
        row = db.execute(
            select(Payment, Invoice, Student).join(Invoice, Payment.invoice_id == Invoice.id)
            .join(Student, Invoice.student_id == Student.id).where(Payment.id == entry.ref_id)
        ).first()
        if row is None:
            raise not_found
        p, inv, s = row
        return {"kind": RECEIPT, "valid": True, "number": p.receipt_number, "school_name": school,
                "issued_on": p.created_at.date(), "student_name": _student_name(s),
                "details": {"Objet": inv.label, "Montant reçu": f"{float(p.amount):,.0f} F CFA".replace(",", " ")}}
    cert = db.execute(select(Certificate).where(Certificate.id == entry.ref_id)).scalar_one_or_none()
    if cert is None:
        raise not_found
    return {"kind": CERTIFICATE, "valid": cert.voided_at is None, "number": cert.number, "school_name": school,
            "issued_on": cert.created_at.date(), "student_name": cert.snapshot["student_name"],
            "details": {"Classe": cert.snapshot["class_name"], "Année scolaire": cert.snapshot["academic_year"]},
            "voided_on": cert.voided_at.date() if cert.voided_at else None}
