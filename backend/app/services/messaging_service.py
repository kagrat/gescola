"""Messagerie école ↔ familles et annonces.

Règles de sécurité (chacune est couverte par un test) :
  * un fil est TOUJOURS rattaché à un élève et ses participants sont explicites ;
    on ne lit, ne répond et ne compte que les fils dont on est participant — un
    fil étranger répond 404, jamais 403 (on ne confirme pas son existence) ;
  * un parent ne conserve l'accès à un fil que tant qu'il reste rattaché à
    l'élève (retirer le rattachement ferme l'accès, y compris aux fils passés) ;
  * un parent n'écrit qu'aux contacts de SON enfant (Direction, Censeur,
    Surveillant, Secrétariat, Comptabilité, enseignants de sa classe) — jamais à
    un membre du personnel choisi arbitrairement, ni au Fondateur ;
  * un enseignant n'écrit qu'aux parents d'élèves de SES classes (affectation ou
    professeur principal) ; les autres rôles autorisés écrivent au sujet de
    n'importe quel élève de l'établissement ;
  * seul le personnel peut émettre une convocation ;
  * le contenu des messages n'est jamais écrit dans le journal d'audit ; les
    messages ne sont ni modifiables ni supprimables.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.roles import CAN_MANAGE_USERS, CAN_MESSAGE_GUARDIANS, PARENT_CONTACT_ROLES
from app.models.academic import SchoolClass, Subject
from app.models.guardian_link import GuardianLink
from app.models.messaging import Announcement, Message, MessageThread, ThreadKind, ThreadParticipant
from app.models.student import Student
from app.models.teaching import TeacherAssignment
from app.models.user import User, UserRole
from app.schemas.messaging import (
    AnnouncementCreate, AnnouncementOut, ContactOut, MessageOut, ParticipantOut, ThreadCreate, ThreadDetailOut,
    ThreadSummaryOut,
)
from app.services.audit_service import log_action
from app.services.guardian_service import assert_parent_linked_to_student

MAX_PARENT_RECIPIENTS = 3
_ROLE_LABELS = {
    UserRole.SCHOOL_ADMIN: "Direction", UserRole.CENSOR: "Censeur", UserRole.SUPERVISOR: "Surveillance",
    UserRole.STAFF: "Secrétariat", UserRole.ACCOUNTANT: "Comptabilité",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable.")


def _get_student(db: Session, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    student = db.execute(select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Élève introuvable.")
    return student


# ---------------- Qui peut écrire à qui ----------------

def active_guardians(db: Session, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[tuple[User, str]]:
    rows = db.execute(
        select(User, GuardianLink.relationship_label)
        .join(GuardianLink, GuardianLink.parent_user_id == User.id)
        .where(
            GuardianLink.tenant_id == tenant_id, GuardianLink.student_id == student_id,
            User.is_active.is_(True), User.role == UserRole.PARENT,
        )
        .order_by(User.full_name)
    ).all()
    return [(user, label) for user, label in rows]


def _teacher_teaches_student(db: Session, tenant_id: uuid.UUID, teacher_id: uuid.UUID, student: Student) -> bool:
    if student.class_id is None:
        return False
    is_head = db.execute(
        select(SchoolClass.id).where(
            SchoolClass.id == student.class_id, SchoolClass.tenant_id == tenant_id, SchoolClass.head_teacher_id == teacher_id
        )
    ).first() is not None
    if is_head:
        return True
    return db.execute(
        select(TeacherAssignment.id).where(
            TeacherAssignment.tenant_id == tenant_id, TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.class_id == student.class_id,
        )
    ).first() is not None


def can_message_about(db: Session, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, student: Student) -> bool:
    if actor_role == UserRole.TEACHER:
        return _teacher_teaches_student(db, tenant_id, actor_id, student)
    return actor_role in CAN_MESSAGE_GUARDIANS


def parent_contacts(db: Session, tenant_id: uuid.UUID, student: Student) -> list[ContactOut]:
    """Contacts de l'établissement proposés à un parent au sujet de cet enfant."""
    contacts: list[ContactOut] = []
    staff = db.execute(
        select(User).where(User.tenant_id == tenant_id, User.is_active.is_(True), User.role.in_(PARENT_CONTACT_ROLES))
        .order_by(User.full_name)
    ).scalars().all()
    contacts += [ContactOut(id=u.id, full_name=u.full_name, role=u.role, detail=_ROLE_LABELS.get(u.role)) for u in staff]

    if student.class_id is not None:
        head_id = db.execute(select(SchoolClass.head_teacher_id).where(SchoolClass.id == student.class_id)).scalar_one_or_none()
        subjects: dict[uuid.UUID, list[str]] = {}
        for teacher_id, subject_name in db.execute(
            select(TeacherAssignment.teacher_id, Subject.name)
            .join(Subject, Subject.id == TeacherAssignment.subject_id)
            .where(TeacherAssignment.tenant_id == tenant_id, TeacherAssignment.class_id == student.class_id)
            .order_by(Subject.name)
        ).all():
            subjects.setdefault(teacher_id, []).append(subject_name)
        teacher_ids = set(subjects) | ({head_id} if head_id else set())
        if teacher_ids:
            teachers = db.execute(
                select(User).where(User.id.in_(teacher_ids), User.tenant_id == tenant_id, User.is_active.is_(True), User.role == UserRole.TEACHER)
                .order_by(User.full_name)
            ).scalars().all()
            for t in teachers:
                parts = (["Professeur principal"] if t.id == head_id else []) + subjects.get(t.id, [])
                contacts.append(ContactOut(id=t.id, full_name=t.full_name, role=t.role, detail=" · ".join(parts) or "Enseignant"))
    return contacts


def contacts_for_parent(db: Session, *, tenant_id: uuid.UUID, parent_id: uuid.UUID, student_id: uuid.UUID) -> list[ContactOut]:
    assert_parent_linked_to_student(db, tenant_id=tenant_id, parent_user_id=parent_id, student_id=student_id)
    return parent_contacts(db, tenant_id, _get_student(db, tenant_id, student_id))


def guardians_for_staff(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, student_id: uuid.UUID,
) -> list[ContactOut]:
    student = _get_student(db, tenant_id, student_id)
    if not can_message_about(db, tenant_id, actor_id, actor_role, student):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez écrire qu'aux parents d'élèves de vos classes.")
    return [ContactOut(id=u.id, full_name=u.full_name, role=u.role, detail=label) for u, label in active_guardians(db, tenant_id, student_id)]


# ---------------- Création ----------------

def create_thread(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, data: ThreadCreate) -> uuid.UUID:
    student = _get_student(db, tenant_id, data.student_id)

    if actor_role == UserRole.PARENT:
        assert_parent_linked_to_student(db, tenant_id=tenant_id, parent_user_id=actor_id, student_id=student.id)
        if data.kind != ThreadKind.CONVERSATION:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seul le personnel peut envoyer une convocation.")
        ids = data.recipient_user_ids or []
        if not ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choisissez à qui vous écrivez parmi les contacts de l'établissement.")
        if len(ids) > MAX_PARENT_RECIPIENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vous pouvez écrire à {MAX_PARENT_RECIPIENTS} contacts au plus.")
        allowed = {c.id for c in parent_contacts(db, tenant_id, student)}
        if not set(ids) <= allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce destinataire ne fait pas partie des contacts de votre enfant.")
        recipients = ids
    elif actor_role in CAN_MESSAGE_GUARDIANS:
        if not can_message_about(db, tenant_id, actor_id, actor_role, student):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez écrire qu'aux parents d'élèves de vos classes.")
        guardian_ids = {u.id for u, _ in active_guardians(db, tenant_id, student.id)}
        if not guardian_ids:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Aucun parent (actif) n'est rattaché à cet élève.")
        if data.recipient_user_ids is None:
            recipients = sorted(guardian_ids, key=str)
        else:
            if not set(data.recipient_user_ids) <= guardian_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un destinataire n'est pas un parent rattaché à cet élève.")
            recipients = data.recipient_user_ids
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissions insuffisantes pour cette action.")

    now = _now()
    thread = MessageThread(
        tenant_id=tenant_id, student_id=student.id, created_by=actor_id, subject=data.subject, kind=data.kind,
        meeting_at=data.meeting_at, meeting_place=data.meeting_place, last_message_at=now,
    )
    db.add(thread)
    db.flush()
    db.add(ThreadParticipant(tenant_id=tenant_id, thread_id=thread.id, user_id=actor_id, last_read_at=now))
    for user_id in recipients:
        db.add(ThreadParticipant(tenant_id=tenant_id, thread_id=thread.id, user_id=user_id, last_read_at=None))
    db.add(Message(tenant_id=tenant_id, thread_id=thread.id, sender_id=actor_id, body=data.body, created_at=now))
    # Le contenu n'est JAMAIS journalisé : seulement le fait, l'élève concerné et le nombre de destinataires.
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="message_thread.created", target_type="MessageThread",
        target_id=str(thread.id), metadata={"student_id": str(student.id), "kind": data.kind.value, "recipients": len(recipients)},
    )
    db.commit()
    return thread.id


# ---------------- Accès ----------------

def _still_linked(db: Session, tenant_id: uuid.UUID, parent_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    return db.execute(
        select(GuardianLink.id).where(
            GuardianLink.tenant_id == tenant_id, GuardianLink.parent_user_id == parent_id, GuardianLink.student_id == student_id
        )
    ).first() is not None


def _participant_thread(
    db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, thread_id: uuid.UUID,
) -> tuple[ThreadParticipant, MessageThread]:
    row = db.execute(
        select(ThreadParticipant, MessageThread)
        .join(MessageThread, MessageThread.id == ThreadParticipant.thread_id)
        .where(ThreadParticipant.thread_id == thread_id, ThreadParticipant.user_id == user_id, ThreadParticipant.tenant_id == tenant_id)
    ).one_or_none()
    if row is None:
        raise _not_found()
    participant, thread = row
    # Un parent perd l'accès dès que son rattachement à l'élève est retiré (fils passés compris).
    if role == UserRole.PARENT and not _still_linked(db, tenant_id, user_id, thread.student_id):
        raise _not_found()
    return participant, thread


def _visible_threads(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole):
    query = (
        select(MessageThread, Student.first_name, Student.last_name)
        .join(ThreadParticipant, ThreadParticipant.thread_id == MessageThread.id)
        .join(Student, Student.id == MessageThread.student_id)
        .where(ThreadParticipant.user_id == user_id, MessageThread.tenant_id == tenant_id)
    )
    if role == UserRole.PARENT:
        query = query.where(
            exists().where(
                GuardianLink.parent_user_id == user_id, GuardianLink.student_id == MessageThread.student_id,
                GuardianLink.tenant_id == tenant_id,
            )
        )
    return query.order_by(MessageThread.last_message_at.desc())


def _unread_thread_ids(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.execute(
            select(Message.thread_id)
            .join(ThreadParticipant, ThreadParticipant.thread_id == Message.thread_id)
            .where(
                ThreadParticipant.user_id == user_id, Message.tenant_id == tenant_id, Message.sender_id != user_id,
                or_(ThreadParticipant.last_read_at.is_(None), Message.created_at > ThreadParticipant.last_read_at),
            )
            .distinct()
        ).scalars().all()
    )


def list_threads(
    db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, unread_only: bool = False,
) -> list[ThreadSummaryOut]:
    rows = db.execute(_visible_threads(db, tenant_id, user_id, role)).all()
    if not rows:
        return []
    thread_ids = [t.id for t, _, _ in rows]
    unread = _unread_thread_ids(db, tenant_id, user_id)

    last_messages = {
        m.thread_id: m
        for m in db.execute(
            select(Message).where(Message.thread_id.in_(thread_ids)).order_by(Message.thread_id, Message.created_at.desc())
            .distinct(Message.thread_id)
        ).scalars().all()
    }
    names: dict[uuid.UUID, list[str]] = {}
    for thread_id, full_name in db.execute(
        select(ThreadParticipant.thread_id, User.full_name)
        .join(User, User.id == ThreadParticipant.user_id)
        .where(ThreadParticipant.thread_id.in_(thread_ids), ThreadParticipant.user_id != user_id)
        .order_by(User.full_name)
    ).all():
        names.setdefault(thread_id, []).append(full_name)

    summaries = []
    for thread, first_name, last_name in rows:
        is_unread = thread.id in unread
        if unread_only and not is_unread:
            continue
        last = last_messages[thread.id]
        preview = last.body.replace("\n", " ")
        summaries.append(ThreadSummaryOut(
            id=thread.id, student_id=thread.student_id, student_name=f"{last_name.upper()} {first_name}", subject=thread.subject,
            kind=thread.kind, meeting_at=thread.meeting_at, last_message_at=thread.last_message_at,
            last_message_preview=preview[:140] + ("…" if len(preview) > 140 else ""), last_message_sender_id=last.sender_id,
            unread=is_unread, participant_names=names.get(thread.id, []),
        ))
    return summaries


def unread_count(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole) -> int:
    visible = {t.id for t, _, _ in db.execute(_visible_threads(db, tenant_id, user_id, role)).all()}
    return len(visible & _unread_thread_ids(db, tenant_id, user_id))


def get_thread(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, thread_id: uuid.UUID) -> ThreadDetailOut:
    _, thread = _participant_thread(db, tenant_id, user_id, role, thread_id)
    student = db.get(Student, thread.student_id)
    participants = db.execute(
        select(ThreadParticipant, User).join(User, User.id == ThreadParticipant.user_id)
        .where(ThreadParticipant.thread_id == thread.id).order_by(User.full_name)
    ).all()
    messages = db.execute(
        select(Message, User).join(User, User.id == Message.sender_id)
        .where(Message.thread_id == thread.id).order_by(Message.created_at)
    ).all()
    return ThreadDetailOut(
        id=thread.id, student_id=thread.student_id, student_name=f"{student.last_name.upper()} {student.first_name}",
        subject=thread.subject, kind=thread.kind, meeting_at=thread.meeting_at, meeting_place=thread.meeting_place,
        created_by=thread.created_by,
        participants=[ParticipantOut(user_id=u.id, full_name=u.full_name, role=u.role, last_read_at=p.last_read_at) for p, u in participants],
        messages=[MessageOut(id=m.id, sender_id=u.id, sender_name=u.full_name, sender_role=u.role, body=m.body, created_at=m.created_at) for m, u in messages],
    )


def mark_read(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, thread_id: uuid.UUID) -> None:
    participant, thread = _participant_thread(db, tenant_id, user_id, role, thread_id)
    # On marque « lu » jusqu'au dernier message existant (pas jusqu'à « maintenant ») : un message qui
    # arrive pendant que la personne lit reste non lu.
    latest = db.execute(select(func.max(Message.created_at)).where(Message.thread_id == thread.id)).scalar_one()
    if participant.last_read_at is None or (latest and latest > participant.last_read_at):
        participant.last_read_at = latest
        db.commit()


def send_message(
    db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, thread_id: uuid.UUID, body: str,
) -> MessageOut:
    participant, thread = _participant_thread(db, tenant_id, user_id, role, thread_id)
    sender = db.get(User, user_id)
    now = _now()
    message = Message(tenant_id=tenant_id, thread_id=thread.id, sender_id=user_id, body=body, created_at=now)
    db.add(message)
    thread.last_message_at = now
    participant.last_read_at = now   # écrire dans un fil vaut lecture
    db.commit()
    db.refresh(message)
    return MessageOut(id=message.id, sender_id=user_id, sender_name=sender.full_name, sender_role=sender.role, body=body, created_at=message.created_at)


# ---------------- Annonces ----------------

def _announcement_out(a: Announcement, author_name: str, class_name: str | None) -> AnnouncementOut:
    return AnnouncementOut(
        id=a.id, author_id=a.author_id, author_name=author_name, class_id=a.class_id, class_name=class_name,
        title=a.title, body=a.body, created_at=a.created_at,
    )


def create_announcement(db: Session, *, tenant_id: uuid.UUID, actor: User, data: AnnouncementCreate) -> AnnouncementOut:
    class_name = None
    if data.class_id is not None:
        school_class = db.execute(
            select(SchoolClass).where(SchoolClass.id == data.class_id, SchoolClass.tenant_id == tenant_id)
        ).scalar_one_or_none()
        if school_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable.")
        class_name = school_class.name
    announcement = Announcement(tenant_id=tenant_id, author_id=actor.id, class_id=data.class_id, title=data.title, body=data.body)
    db.add(announcement)
    db.flush()
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor.id, action="announcement.published", target_type="Announcement",
        target_id=str(announcement.id), metadata={"class_id": str(data.class_id) if data.class_id else None},
    )
    db.commit()
    db.refresh(announcement)
    return _announcement_out(announcement, actor.full_name, class_name)


def list_announcements(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole) -> list[AnnouncementOut]:
    query = (
        select(Announcement, User.full_name, SchoolClass.name)
        .join(User, User.id == Announcement.author_id)
        .outerjoin(SchoolClass, SchoolClass.id == Announcement.class_id)
        .where(Announcement.tenant_id == tenant_id)
        .order_by(Announcement.created_at.desc())
    )
    if role == UserRole.PARENT:
        # Un parent voit les annonces de l'établissement et celles des classes de SES enfants rattachés.
        children_classes = (
            select(Student.class_id)
            .join(GuardianLink, GuardianLink.student_id == Student.id)
            .where(GuardianLink.parent_user_id == user_id, GuardianLink.tenant_id == tenant_id, Student.class_id.is_not(None))
        )
        query = query.where(or_(Announcement.class_id.is_(None), Announcement.class_id.in_(children_classes)))
    return [_announcement_out(a, author, class_name) for a, author, class_name in db.execute(query).all()]


def delete_announcement(db: Session, *, tenant_id: uuid.UUID, actor: User, announcement_id: uuid.UUID) -> None:
    announcement = db.execute(
        select(Announcement).where(Announcement.id == announcement_id, Announcement.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annonce introuvable.")
    # L'auteur retire sa propre annonce ; la Direction et le Fondateur peuvent retirer n'importe laquelle.
    if announcement.author_id != actor.id and actor.role not in CAN_MANAGE_USERS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez retirer que vos propres annonces.")
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor.id, action="announcement.deleted", target_type="Announcement",
        target_id=str(announcement.id), metadata={"author_id": str(announcement.author_id)},
    )
    db.delete(announcement)
    db.commit()
