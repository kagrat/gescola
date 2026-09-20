import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.canteen import CanteenSubscriptionStatus


class CanteenPlanCreate(BaseModel):
    name: str
    price_per_month: float

    @field_validator("price_per_month")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Le prix doit être strictement positif.")
        return v


class CanteenPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    price_per_month: float


class CanteenSubscriptionCreate(BaseModel):
    student_id: uuid.UUID
    plan_id: uuid.UUID
    month: str  # "YYYY-MM"

    @field_validator("month")
    @classmethod
    def valid_month(cls, v: str) -> str:
        try:
            date.fromisoformat(f"{v}-01")
        except ValueError:
            raise ValueError("Le mois doit être au format AAAA-MM.")
        return v


class CanteenSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    plan_id: uuid.UUID
    invoice_id: uuid.UUID
    month: str
    status: CanteenSubscriptionStatus
