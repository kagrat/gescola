import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.attendance import AttendanceStatus


class GradeCreate(BaseModel):
    student_id: uuid.UUID
    subject_id: uuid.UUID
    term: str
    evaluation_label: str
    value: float
    coefficient: float = 1

    @field_validator("value")
    @classmethod
    def value_range(cls, v: float) -> float:
        if not (0 <= v <= 20):
            raise ValueError("La note doit être comprise entre 0 et 20.")
        return v

    @field_validator("coefficient")
    @classmethod
    def coefficient_range(cls, v: float) -> float:
        if not (0 < v <= 20):
            raise ValueError("Le coefficient doit être compris entre 0 (exclu) et 20.")
        return v


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    term: str
    evaluation_label: str
    value: float
    coefficient: float
    is_locked: bool


class StudentAverageOut(BaseModel):
    student_id: uuid.UUID
    term: str
    subject_averages: dict[str, float]
    general_average: float


class AttendanceCreate(BaseModel):
    student_id: uuid.UUID
    date: date
    status: AttendanceStatus
    justified: bool = False


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    date: date
    status: AttendanceStatus
    justified: bool
