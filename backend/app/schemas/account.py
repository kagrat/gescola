import uuid

from pydantic import BaseModel, EmailStr, field_validator

from app.core.security import validate_password_strength
from app.models.user import UserRole


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError(" ".join(errors))
        return v


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: UserRole | None = None

    @field_validator("full_name")
    @classmethod
    def not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Le nom ne peut pas être vide.")
        return v.strip() if v else v


class TemporaryPasswordOut(BaseModel):
    """Le mot de passe provisoire n'est affiché qu'UNE fois, dans cette réponse :
    il n'est ni conservé en clair ni écrit dans le journal d'audit."""

    user_id: uuid.UUID
    temporary_password: str
    must_change_password: bool = True
