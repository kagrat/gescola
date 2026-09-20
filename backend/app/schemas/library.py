import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class BookCreate(BaseModel):
    title: str
    author: str
    isbn: str | None = None
    total_copies: int = 1


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    author: str
    isbn: str | None
    total_copies: int
    available_copies: int


class LoanCreate(BaseModel):
    book_id: uuid.UUID
    student_id: uuid.UUID
    due_at: date


class LoanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    book_id: uuid.UUID
    student_id: uuid.UUID
    loaned_at: date
    due_at: date
    returned_at: date | None
