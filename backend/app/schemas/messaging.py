import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, field_validator, model_validator

from app.models.messaging import ThreadKind
from app.models.user import UserRole

MAX_BODY_LENGTH = 5000
MAX_SUBJECT_LENGTH = 200


def _clean(value: str, *, label: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} ne peut pas être vide.")
    if len(value) > max_length:
        raise ValueError(f"{label} ne peut pas dépasser {max_length} caractères.")
    return value


class ThreadCreate(BaseModel):
    student_id: uuid.UUID
    subject: str
    body: str
    kind: ThreadKind = ThreadKind.CONVERSATION
    # Personnel → parents : parents destinataires (par défaut, tous les parents rattachés à l'élève).
    # Parent → école : contacts de l'établissement choisis (1 à 3).
    recipient_user_ids: list[uuid.UUID] | None = None
    meeting_at: datetime | None = None
    meeting_place: str | None = None

    @field_validator("subject")
    @classmethod
    def clean_subject(cls, v: str) -> str:
        return _clean(v, label="L'objet", max_length=MAX_SUBJECT_LENGTH)

    @field_validator("body")
    @classmethod
    def clean_body(cls, v: str) -> str:
        return _clean(v, label="Le message", max_length=MAX_BODY_LENGTH)

    @field_validator("recipient_user_ids")
    @classmethod
    def unique_recipients(cls, v: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if v is None:
            return None
        if not v:
            raise ValueError("Choisissez au moins un destinataire.")
        if len(set(v)) != len(v):
            raise ValueError("Un destinataire est indiqué plusieurs fois.")
        if len(v) > 50:
            raise ValueError("Trop de destinataires.")
        return v

    @field_validator("meeting_place")
    @classmethod
    def clean_place(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v[:200] or None

    @model_validator(mode="after")
    def check_convocation(self) -> "ThreadCreate":
        if self.kind == ThreadKind.CONVOCATION:
            if self.meeting_at is None:
                raise ValueError("Une convocation doit indiquer la date et l'heure du rendez-vous.")
            when = self.meeting_at if self.meeting_at.tzinfo else self.meeting_at.replace(tzinfo=timezone.utc)
            if when < datetime.now(timezone.utc):
                raise ValueError("La date d'une convocation doit être dans le futur.")
        elif self.meeting_at is not None or self.meeting_place:
            raise ValueError("La date et le lieu ne concernent que les convocations.")
        return self


class MessageCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def clean_body(cls, v: str) -> str:
        return _clean(v, label="Le message", max_length=MAX_BODY_LENGTH)


class ParticipantOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    role: UserRole
    last_read_at: datetime | None


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    sender_role: UserRole
    body: str
    created_at: datetime


class ThreadSummaryOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    subject: str
    kind: ThreadKind
    meeting_at: datetime | None
    last_message_at: datetime
    last_message_preview: str
    last_message_sender_id: uuid.UUID
    unread: bool
    participant_names: list[str]


class ThreadDetailOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    subject: str
    kind: ThreadKind
    meeting_at: datetime | None
    meeting_place: str | None
    created_by: uuid.UUID
    participants: list[ParticipantOut]
    messages: list[MessageOut]


class UnreadCountOut(BaseModel):
    unread: int


class ContactOut(BaseModel):
    """Contact de l'établissement proposé à un parent, ou parent proposé au personnel."""

    id: uuid.UUID
    full_name: str
    role: UserRole
    detail: str | None = None  # ex. « Professeur principal », « Mathématiques », « Mère »


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    class_id: uuid.UUID | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        return _clean(v, label="Le titre", max_length=MAX_SUBJECT_LENGTH)

    @field_validator("body")
    @classmethod
    def clean_body(cls, v: str) -> str:
        return _clean(v, label="Le texte de l'annonce", max_length=MAX_BODY_LENGTH)


class AnnouncementOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    class_id: uuid.UUID | None
    class_name: str | None
    title: str
    body: str
    created_at: datetime
