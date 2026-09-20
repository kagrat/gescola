import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.security import validate_password_strength


class NetworkCreate(BaseModel):
    name: str
    code: str


class NetworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str


class NetworkAdminCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError(" ".join(errors))
        return v


class SchoolSnapshot(BaseModel):
    tenant_id: str
    name: str
    code: str
    active_students: int
    staff_count: int
    revenue_due: float
    revenue_collected: float
    recovery_rate_percent: float | None


class NetworkTotals(BaseModel):
    school_count: int
    active_students: int
    revenue_due: float
    revenue_collected: float
    recovery_rate_percent: float | None


class NetworkOverviewOut(BaseModel):
    network: NetworkOut
    schools: list[SchoolSnapshot]
    totals: NetworkTotals
