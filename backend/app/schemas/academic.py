import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.academic import SchoolCycle
from app.models.student import StudentStatus


class SchoolClassCreate(BaseModel):
    name: str
    level: str
    cycle: SchoolCycle = SchoolCycle.PRIMAIRE


class SchoolClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    level: str
    cycle: SchoolCycle


class SubjectCreate(BaseModel):
    name: str
    default_coefficient: float = 1

    @field_validator("default_coefficient")
    @classmethod
    def coefficient_range(cls, v: float) -> float:
        if not (0 < v <= 20):
            raise ValueError("Le coefficient doit être compris entre 0 (exclu) et 20.")
        return v


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    default_coefficient: float


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    class_id: uuid.UUID | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    guardian_email: EmailStr | None = None


class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    class_id: uuid.UUID | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    guardian_email: EmailStr | None = None
    status: StudentStatus | None = None


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date | None
    class_id: uuid.UUID | None
    guardian_name: str | None
    guardian_phone: str | None
    guardian_email: str | None
    status: StudentStatus
