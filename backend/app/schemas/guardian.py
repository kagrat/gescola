import uuid

from pydantic import BaseModel, ConfigDict


class GuardianLinkCreate(BaseModel):
    parent_user_id: uuid.UUID
    student_id: uuid.UUID
    relationship_label: str


class GuardianLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    parent_user_id: uuid.UUID
    student_id: uuid.UUID
    relationship_label: str


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
