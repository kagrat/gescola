from pydantic import BaseModel, EmailStr, field_validator

from app.core.security import validate_password_strength


class SignupRequest(BaseModel):
    school_name: str
    admin_full_name: str
    admin_email: EmailStr
    admin_password: str

    @field_validator("school_name", "admin_full_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Ce champ ne peut pas être vide.")
        return v.strip()

    @field_validator("admin_password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError(" ".join(errors))
        return v


class SignupResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant_id: str
    trial_ends_at: str
