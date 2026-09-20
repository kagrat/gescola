import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.security import validate_password_strength
from app.models.user import UserRole


class TenantCreate(BaseModel):
    name: str
    code: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole

    @field_validator("password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError(" ".join(errors))
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    email: str
    full_name: str
    role: UserRole
    is_active: bool
