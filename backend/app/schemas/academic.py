import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.academic import SchoolCycle
from app.models.student import StudentGender, StudentStatus


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
    head_teacher_id: uuid.UUID | None


class SchoolClassUpdate(BaseModel):
    name: str | None = None
    level: str | None = None
    cycle: SchoolCycle | None = None
    head_teacher_id: uuid.UUID | None = None


class SubjectCreate(BaseModel):
    name: str
    default_coefficient: float = 1

    @field_validator("default_coefficient")
    @classmethod
    def coefficient_range(cls, v: float) -> float:
        if not (0 < v <= 20):
            raise ValueError("Le coefficient doit être compris entre 0 (exclu) et 20.")
        return v


class SubjectUpdate(BaseModel):
    name: str | None = None
    default_coefficient: float | None = None

    @field_validator("default_coefficient")
    @classmethod
    def coefficient_range(cls, v: float | None) -> float | None:
        if v is not None and not (0 < v <= 20):
            raise ValueError("Le coefficient doit être compris entre 0 (exclu) et 20.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Le nom de la matière ne peut pas être vide.")
        return v.strip() if v else v


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    default_coefficient: float


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    matricule: str | None = None
    gender: StudentGender | None = None
    is_repeater: bool = False
    class_id: uuid.UUID | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    guardian_email: EmailStr | None = None


class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    matricule: str | None = None
    gender: StudentGender | None = None
    is_repeater: bool | None = None
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
    matricule: str | None
    gender: StudentGender | None
    is_repeater: bool
    class_id: uuid.UUID | None
    guardian_name: str | None
    guardian_phone: str | None
    guardian_email: str | None
    status: StudentStatus
