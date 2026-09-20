import uuid
from datetime import time

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.timetable import Weekday


class TimetableSlotCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    day_of_week: Weekday
    start_time: time
    end_time: time
    room: str | None = None

    @model_validator(mode="after")
    def check_time_order(self) -> "TimetableSlotCreate":
        if self.end_time <= self.start_time:
            raise ValueError("L'heure de fin doit etre apres l'heure de debut.")
        return self


class TimetableSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    day_of_week: Weekday
    start_time: time
    end_time: time
    room: str | None
