import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.report_card import ReportCardStatus
from app.schemas.establishment import VALID_TERMS


def _check_term(v: str) -> str:
    if v not in VALID_TERMS:
        raise ValueError("La période doit être T1, T2 ou T3.")
    return v


class GenerateRequest(BaseModel):
    class_id: uuid.UUID
    term: str

    _term = field_validator("term")(_check_term)


class GenerateResult(BaseModel):
    created: int
    updated: int
    skipped_published: int


class RemarksUpdate(BaseModel):
    principal_comment: str | None = None
    council_decision: str | None = None

    @field_validator("principal_comment")
    @classmethod
    def clean_comment(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if len(v) > 1000:
            raise ValueError("L'appréciation ne peut pas dépasser 1000 caractères.")
        return v or None

    @field_validator("council_decision")
    @classmethod
    def clean_decision(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if len(v) > 200:
            raise ValueError("La décision ne peut pas dépasser 200 caractères.")
        return v or None


class ReportCardSummaryOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    class_id: uuid.UUID
    class_name: str
    term: str
    academic_year: str
    status: ReportCardStatus
    general_average: float | None
    rank: int | None
    class_size: int
    published_at: datetime | None


class ReportCardOut(ReportCardSummaryOut):
    snapshot: dict
    principal_comment: str | None
    council_decision: str | None


class AppreciationUpsert(BaseModel):
    student_id: uuid.UUID
    subject_id: uuid.UUID
    term: str
    text: str

    _term = field_validator("term")(_check_term)

    @field_validator("text")
    @classmethod
    def limit(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 300:
            raise ValueError("L'appréciation ne peut pas dépasser 300 caractères.")
        return v


class AppreciationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_id: uuid.UUID
    subject_id: uuid.UUID
    term: str
    text: str
