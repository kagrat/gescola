from pydantic import BaseModel, field_validator

from app.core.image_validation import validate_image_data_uri


class MySignatureOut(BaseModel):
    signature_base64: str | None
    stamp_base64: str | None


class MySignatureUpdate(BaseModel):
    signature_base64: str | None = None
    stamp_base64: str | None = None

    @field_validator("signature_base64", "stamp_base64")
    @classmethod
    def check_image(cls, v: str | None) -> str | None:
        return validate_image_data_uri(v)
