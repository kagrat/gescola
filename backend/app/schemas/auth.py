from pydantic import BaseModel, EmailStr, field_validator

from app.core.security import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Réponse de /auth/login : soit des jetons complets, soit une demande de
    code MFA (mfa_required=True) — jamais les deux."""
    mfa_required: bool = False
    mfa_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class MfaLoginVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaConfirmRequest(BaseModel):
    code: str


class MfaDisableRequest(BaseModel):
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        errors = validate_password_strength(v)
        if errors:
            raise ValueError(" ".join(errors))
        return v
