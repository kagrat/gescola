import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator


class LessonLogEntryCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    session_date: date
    content: str

    @field_validator("content")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le contenu de la séance ne peut pas être vide.")
        return v.strip()


class LessonLogEntryUpdate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le contenu de la séance ne peut pas être vide.")
        return v.strip()


class LessonLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    session_date: date
    content: str


class HomeworkCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    title: str
    description: str
    due_date: date

    @field_validator("title", "description")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Ce champ ne peut pas être vide.")
        return v.strip()


class HomeworkUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: date | None = None


class HomeworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    title: str
    description: str
    due_date: date
