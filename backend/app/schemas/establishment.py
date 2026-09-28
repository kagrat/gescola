import re
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.image_validation import validate_image_data_uri

VALID_TERMS = ("T1", "T2", "T3")


class TermPeriod(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def check_order(self) -> "TermPeriod":
        if self.end < self.start:
            raise ValueError("La fin d'une période ne peut pas précéder son début.")
        return self


def _blank_to_none(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class EstablishmentSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    trade_name: str | None
    rccm: str | None
    ifu: str | None
    address: str | None
    logo_base64: str | None
    # Réglages du bulletin
    academic_year: str | None
    bulletin_motto: str | None
    bulletin_authority_header: str | None
    bulletin_place: str | None
    bulletin_show_appreciations: bool
    bulletin_show_school_life: bool
    bulletin_show_head_teacher_signature: bool
    term_periods: dict[str, TermPeriod] | None
    bulletin_director_user_id: uuid.UUID | None
    bulletin_censor_user_id: uuid.UUID | None


class EstablishmentSettingsUpdate(BaseModel):
    trade_name: str | None = None
    rccm: str | None = None
    ifu: str | None = None
    address: str | None = None
    logo_base64: str | None = None
    academic_year: str | None = None
    bulletin_motto: str | None = None
    bulletin_authority_header: str | None = None
    bulletin_place: str | None = None
    bulletin_show_appreciations: bool | None = None
    bulletin_show_school_life: bool | None = None
    bulletin_show_head_teacher_signature: bool | None = None
    term_periods: dict[str, TermPeriod] | None = None
    bulletin_director_user_id: uuid.UUID | None = None
    bulletin_censor_user_id: uuid.UUID | None = None

    @field_validator("logo_base64")
    @classmethod
    def check_logo(cls, v: str | None) -> str | None:
        return validate_image_data_uri(v)

    @field_validator("bulletin_motto", "bulletin_authority_header", "bulletin_place")
    @classmethod
    def clean_text(cls, v: str | None) -> str | None:
        return _blank_to_none(v)

    @field_validator("academic_year")
    @classmethod
    def check_year(cls, v: str | None) -> str | None:
        v = _blank_to_none(v)
        if v is None:
            return None
        m = re.fullmatch(r"(\d{4})-(\d{4})", v)
        if not m or int(m.group(2)) != int(m.group(1)) + 1:
            raise ValueError("L'année scolaire doit avoir la forme 2026-2027.")
        return v

    @field_validator("term_periods")
    @classmethod
    def check_terms(cls, v: dict[str, TermPeriod] | None) -> dict[str, TermPeriod] | None:
        if v is not None and not set(v) <= set(VALID_TERMS):
            raise ValueError("Les périodes valides sont T1, T2 et T3.")
        return v
