import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.finance import InvoiceStatus, PaymentMethod


class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    label: str
    amount_due: float
    due_date: date
    # Facultatif : par défaut l'année en cours. Une facture peut viser l'année
    # suivante (frais de réinscription facturés avant la rentrée) ou une année
    # passée (régularisation d'arriéré).
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}$")

    @field_validator("amount_due")
    @classmethod
    def positive_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le montant dû doit être strictement positif.")
        return v


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    label: str
    academic_year: str
    amount_due: float
    due_date: date
    status: InvoiceStatus
    amount_paid: float = 0
    balance: float = 0


class PaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: float
    method: PaymentMethod
    reference: str | None = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le montant payé doit être strictement positif.")
        return v


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: float
    method: PaymentMethod
    reference: str | None
    receipt_number: int


# ---------------- Vue financière globale (AU-09) ----------------

class InvoiceRow(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    class_name: str | None
    label: str
    academic_year: str
    amount_due: float
    amount_paid: float
    balance: float
    due_date: date
    state: str            # paid | overdue | partially_paid | pending | cancelled (calculé à la lecture)
    days_overdue: int     # 0 si non échue ou soldée


class ClassFinanceRow(BaseModel):
    class_id: uuid.UUID | None
    class_name: str
    due: float
    paid: float
    outstanding: float
    students_with_balance: int


class FinanceSummary(BaseModel):
    academic_year: str
    due: float
    paid: float
    outstanding: float
    recovery_rate_percent: float | None
    overdue_amount: float
    overdue_invoices: int
    unpaid_invoices: int
    aging: dict[str, float]            # retard : 0-30 j, 31-60 j, 61-90 j, 90+ j
    previous_years_outstanding: float
    by_class: list[ClassFinanceRow]


class BulkInvoiceRequest(BaseModel):
    class_id: uuid.UUID
    label: str = Field(min_length=3, max_length=200)
    amount_due: float
    due_date: date
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}$")

    @field_validator("amount_due")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le montant dû doit être strictement positif.")
        return v

    @field_validator("label")
    @classmethod
    def clean_label(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Le libellé doit contenir au moins 3 caractères.")
        return v


class BulkInvoiceReport(BaseModel):
    dry_run: bool
    class_name: str
    academic_year: str
    students: int            # élèves actifs de la classe
    created: int             # factures créées (ou à créer en aperçu)
    already_billed: int      # élèves déjà facturés avec le même libellé et la même année
    total_amount: float


# ---------------- Reçus et attestations (AU-10) ----------------

class StudentPaymentRow(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_label: str
    amount: float
    method: PaymentMethod
    reference: str | None
    receipt_number: int
    paid_on: date


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    academic_year: str
    number: int
    voided_at: datetime | None = None
    void_reason: str | None = None
    created_at: datetime


class CertificateVoid(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class PublicVerification(BaseModel):
    kind: str
    valid: bool
    number: int
    school_name: str
    issued_on: date
    student_name: str
    details: dict[str, str]
    voided_on: date | None = None


# ---------------- Barème de frais (CP-01) ----------------

class Installment(BaseModel):
    label: str = Field(min_length=2, max_length=60)
    amount: float
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=28)  # ≤ 28 : valable tous les mois, sans cas particulier de février

    @field_validator("amount")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le montant d'une tranche doit être strictement positif.")
        return round(v, 2)

    @field_validator("label")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class FeePlanIn(BaseModel):
    level: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=3, max_length=100)
    installments: list[Installment] = Field(min_length=1, max_length=12)

    @field_validator("level", "name")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("installments")
    @classmethod
    def distinct_labels(cls, v: list[Installment]) -> list[Installment]:
        labels = [i.label.lower() for i in v]
        if len(set(labels)) != len(labels):
            raise ValueError("Deux tranches ne peuvent pas avoir le même libellé.")
        return v


class FeePlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    level: str
    name: str
    installments: list[Installment]
    total: float = 0


class FeePlanApply(BaseModel):
    class_id: uuid.UUID
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}$")


class InstallmentReport(BaseModel):
    label: str
    due_date: date
    created: int
    already_billed: int
    total_amount: float


class FeePlanApplyReport(BaseModel):
    dry_run: bool
    class_name: str
    academic_year: str
    students: int
    discounted_students: int
    exempted_students: int       # remise de 100 % : rien à facturer
    installments: list[InstallmentReport]
    total_amount: float


class FeeDiscountIn(BaseModel):
    percent: float = Field(ge=0, le=100)
    reason: str | None = Field(default=None, max_length=200)
