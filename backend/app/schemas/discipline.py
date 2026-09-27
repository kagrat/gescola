import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.discipline import IncidentCategory, IncidentSeverity, IncidentStatus, SanctionType


class IncidentCreate(BaseModel):
    student_id: uuid.UUID
    occurred_at: datetime
    category: IncidentCategory
    severity: IncidentSeverity
    description: str

    @field_validator("description")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La description de l'incident ne peut pas être vide.")
        return v.strip()


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class SanctionCreate(BaseModel):
    sanction_type: SanctionType
    details: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "SanctionCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("La date de fin ne peut pas précéder la date de début.")
        return self


class SanctionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    imposed_by: uuid.UUID
    sanction_type: SanctionType
    details: str | None
    start_date: date | None
    end_date: date | None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    reported_by: uuid.UUID
    occurred_at: datetime
    category: IncidentCategory
    severity: IncidentSeverity
    description: str
    status: IncidentStatus
    sanctions: list[SanctionOut]
