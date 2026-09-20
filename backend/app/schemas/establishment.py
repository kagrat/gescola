import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.image_validation import validate_image_data_uri


class EstablishmentSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    trade_name: str | None
    rccm: str | None
    ifu: str | None
    address: str | None
    logo_base64: str | None


class EstablishmentSettingsUpdate(BaseModel):
    trade_name: str | None = None
    rccm: str | None = None
    ifu: str | None = None
    address: str | None = None
    logo_base64: str | None = None

    @field_validator("logo_base64")
    @classmethod
    def check_logo(cls, v: str | None) -> str | None:
        return validate_image_data_uri(v)
