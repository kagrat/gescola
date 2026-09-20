import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.finance import InvoiceStatus, PaymentMethod


class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    label: str
    amount_due: float
    due_date: date

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
