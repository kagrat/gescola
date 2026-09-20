import uuid

from pydantic import BaseModel, ConfigDict


class TeacherAssignmentCreate(BaseModel):
    teacher_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID


class TeacherAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    teacher_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
