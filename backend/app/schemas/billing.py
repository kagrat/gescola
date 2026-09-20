import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.billing import PlatformInvoiceStatus, PlatformPaymentMethod, SubscriptionStatus


class PlatformPlanCreate(BaseModel):
    name: str
    code: str
    price_per_month: float
    max_students: int | None = None
    is_default_trial_plan: bool = False

    @field_validator("price_per_month")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Le prix ne peut pas être négatif.")
        return v


class PlatformPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str
    price_per_month: float
    max_students: int | None
    is_default_trial_plan: bool
    is_active: bool


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    plan: PlatformPlanOut
    status: SubscriptionStatus
    effective_status: SubscriptionStatus
    trial_ends_at: date | None
    current_period_end: date | None


class SubscriptionUpdate(BaseModel):
    plan_id: uuid.UUID | None = None
    status: SubscriptionStatus | None = None


class PlatformInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    period_start: date
    period_end: date
    amount_due: float
    due_date: date
    status: PlatformInvoiceStatus
    amount_paid: float = 0
    balance: float = 0


class PlatformPaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: float
    method: PlatformPaymentMethod
    reference: str | None = None

    @field_validator("amount")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le montant doit être strictement positif.")
        return v


class PlatformPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: float
    method: PlatformPaymentMethod
    reference: str | None
