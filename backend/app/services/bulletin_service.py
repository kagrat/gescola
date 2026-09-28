"""Bulletins de notes : génération, publication, appréciations.

Principes :
  * les CHIFFRES d'un bulletin (moyennes, rangs, vie scolaire, appréciations de
    matière, signataires) sont figés dans `ReportCard.snapshot` ; un bulletin
    PUBLIÉ n'est jamais recalculé ni écrasé par une régénération ;
  * publier exige que toutes les notes de l'élève pour la période soient
    verrouillées (c'est le sens du verrouillage : « validation des bulletins »)
    et recalcule le bulletin au moment de la publication, pour ne jamais
    publier des chiffres périmés ;
  * un enseignant ne voit que les bulletins des classes dont il est professeur
    principal ; le secrétariat ne voit que les bulletins publiés ; un parent
    ne voit que les bulletins publiés de ses enfants rattachés.
"""
import hashlib
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.roles import CAN_MANAGE_BULLETINS
from app.models.academic import SchoolClass, Subject
from app.models.attendance import Attendance, AttendanceStatus
from app.models.discipline import Incident
from app.models.grade import Grade
from app.models.report_card import ReportCard, ReportCardAsset, ReportCardStatus, SubjectAppreciation
from app.models.student import Student
from app.models.teaching import TeacherAssignment
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.report_card import (
    AppreciationUpsert, RemarksUpdate, ReportCardOut, ReportCardSummaryOut,
)
from app.services.audit_service import log_action
from app.services.coursework_service import check_assignment_restriction
from app.services.bulletin_pdf import build_report_card_pdf
from app.services.guardian_service import assert_parent_linked_to_student
from app.services.results_service import ClassTermResults, compute_class_term_results

TERM_LABELS = {"T1": "1er Trimestre", "T2": "2e Trimestre", "T3": "3e Trimestre"}


# ---------------- Utilitaires ----------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def default_academic_year(today: date) -> str:
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"


def academic_year_of(tenant: Tenant, today: date | None = None) -> str:
    return tenant.academic_year or default_academic_year(today or date.today())


def _term_window(tenant: Tenant, term: str, year: str, today: date) -> tuple[date, date, bool]:
    """Période sur laquelle compter absences/retards/incidents : celle
    configurée par l'établissement pour ce trimestre, sinon depuis le début
    de l'année scolaire (1er septembre) jusqu'à aujourd'hui."""
    periods = tenant.term_periods or {}
    if term in periods:
        return date.fromisoformat(periods[term]["start"]), date.fromisoformat(periods[term]["end"]), True
    return date(int(year[:4]), 9, 1), today, False


def _resolve_signers(db: Session, tenant: Tenant, school_class: SchoolClass) -> dict:
    """Signataires du bulletin. Le Directeur et le Censeur sont ceux que
    l'établissement a DÉSIGNÉS (Paramètres → Bulletin), s'ils sont toujours
    actifs et du bon rôle ; à défaut, le plus ancien compte actif du rôle
    (Direction, puis Fondateur ; Censeur). Le professeur principal est celui
    désigné sur la classe."""
    tenant_id = tenant.id

    def designated(user_id: uuid.UUID | None, roles: tuple[UserRole, ...]) -> User | None:
        if user_id is None:
            return None
        return db.execute(
            select(User).where(
                User.id == user_id, User.tenant_id == tenant_id, User.role.in_(roles), User.is_active.is_(True)
            )
        ).scalar_one_or_none()

    def oldest(role: UserRole) -> User | None:
        return db.execute(
            select(User).where(User.tenant_id == tenant_id, User.role == role, User.is_active.is_(True))
            .order_by(User.created_at)
        ).scalars().first()

    director = (
        designated(tenant.bulletin_director_user_id, (UserRole.SCHOOL_ADMIN, UserRole.FOUNDER))
        or oldest(UserRole.SCHOOL_ADMIN) or oldest(UserRole.FOUNDER)
    )
    censor = designated(tenant.bulletin_censor_user_id, (UserRole.CENSOR,)) or oldest(UserRole.CENSOR)
    head = None
    if school_class.head_teacher_id:
        head = db.execute(
            select(User).where(User.id == school_class.head_teacher_id, User.tenant_id == tenant_id, User.is_active.is_(True))
        ).scalar_one_or_none()

    def ref(u: User | None) -> dict | None:
        return {"user_id": str(u.id), "name": u.full_name} if u else None

    return {"director": ref(director), "censor": ref(censor), "head_teacher": ref(head)}


def _school_life(db: Session, tenant_id: uuid.UUID, student_id: uuid.UUID, start: date, end: date) -> dict:
    rows = db.execute(
        select(Attendance.status, Attendance.justified, func.count())
        .where(Attendance.tenant_id == tenant_id, Attendance.student_id == student_id,
               Attendance.date >= start, Attendance.date <= end)
        .group_by(Attendance.status, Attendance.justified)
    ).all()
    justified = unjustified = late = 0
    for st, is_justified, count in rows:
        if st == AttendanceStatus.ABSENT:
            if is_justified:
                justified += count
            else:
                unjustified += count
        elif st == AttendanceStatus.LATE:
            late += count
    incidents = db.execute(
        select(func.count()).select_from(Incident).where(
            Incident.tenant_id == tenant_id, Incident.student_id == student_id,
            func.date(Incident.occurred_at) >= start, func.date(Incident.occurred_at) <= end,
        )
    ).scalar_one()
    return {
        "justified_absences": justified, "unjustified_absences": unjustified, "lateness": late,
        "incidents": incidents, "period_start": start.isoformat(), "period_end": end.isoformat(),
    }


def _class_subject_ids(db: Session, tenant_id: uuid.UUID, class_id: uuid.UUID, results: ClassTermResults) -> list[uuid.UUID]:
    """Matières figurant au bulletin d'une classe : celles qui ont au moins une
    note dans la classe pour la période, plus celles affectées à un enseignant
    de cette classe (une matière sans encore aucune note apparaît alors avec « — »)."""
    ids = set(results.subject_class_average)
    ids |= set(
        db.execute(
            select(TeacherAssignment.subject_id).where(TeacherAssignment.tenant_id == tenant_id, TeacherAssignment.class_id == class_id)
        ).scalars().all()
    )
    return sorted(ids, key=lambda i: results.subject_names.get(i, "").lower())


def _build_snapshot(
    db: Session, *, tenant: Tenant, school_class: SchoolClass, student: Student, results: ClassTermResults,
    subject_ids: list[uuid.UUID], term: str, year: str, signers: dict, today: date,
) -> dict:
    appreciations = {
        a.subject_id: a.text
        for a in db.execute(
            select(SubjectAppreciation).where(
                SubjectAppreciation.tenant_id == tenant.id, SubjectAppreciation.student_id == student.id,
                SubjectAppreciation.term == term,
            )
        ).scalars().all()
    }
    own = results.subject_averages.get(student.id, {})
    rows = []
    for subject_id in subject_ids:
        rows.append({
            "subject_id": str(subject_id),
            "name": results.subject_names.get(subject_id, "—"),
            "coefficient": results.coefficients.get(subject_id, 1.0),
            "average": own.get(subject_id),
            "class_average": results.subject_class_average.get(subject_id),
            "rank": results.subject_ranks.get(subject_id, {}).get(student.id),
            "appreciation": appreciations.get(subject_id),
        })
    counted = [r for r in rows if r["average"] is not None]
    highest = max(counted, key=lambda r: r["average"], default=None)
    lowest = min(counted, key=lambda r: r["average"], default=None)
    start, end, configured = _term_window(tenant, term, year, today)
    school_life = _school_life(db, tenant.id, student.id, start, end)
    school_life["period_configured"] = configured
    return {
        "student": {
            "name": f"{student.last_name.upper()} {student.first_name}",
            "matricule": student.matricule,
            "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
            "gender": student.gender.value if student.gender else None,
            "is_repeater": student.is_repeater,
            "class_name": school_class.name,
        },
        "term": term,
        "academic_year": year,
        "subjects": rows,
        "total_coefficients": sum(r["coefficient"] for r in counted),
        "general": {
            "average": results.general_averages.get(student.id),
            "rank": results.general_ranks.get(student.id),
            "class_size": len(results.student_ids),
            "class_average": results.class_average,
            "highest": {"name": highest["name"], "value": highest["average"]} if highest else None,
            "lowest": {"name": lowest["name"], "value": lowest["average"]} if lowest else None,
        },
        "school_life": school_life,
        "signers": signers,
    }


def _get_class_or_404(db: Session, tenant_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
    school_class = db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classe introuvable.")
    return school_class


# ---------------- Génération ----------------

def generate_report_cards(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, class_id: uuid.UUID, term: str,
) -> dict:
    school_class = _get_class_or_404(db, tenant_id, class_id)
    tenant = db.get(Tenant, tenant_id)
    today = date.today()
    year = academic_year_of(tenant, today)

    results = compute_class_term_results(db, tenant_id=tenant_id, class_id=class_id, term=term)
    if not results.student_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Aucun élève actif dans cette classe.")

    students = db.execute(select(Student).where(Student.id.in_(results.student_ids))).scalars().all()
    existing = {
        c.student_id: c
        for c in db.execute(
            select(ReportCard).where(
                ReportCard.tenant_id == tenant_id, ReportCard.student_id.in_(results.student_ids),
                ReportCard.term == term, ReportCard.academic_year == year,
            )
        ).scalars().all()
    }
    subject_ids = _class_subject_ids(db, tenant_id, class_id, results)
    signers = _resolve_signers(db, tenant, school_class)

    created = updated = skipped = 0
    for student in students:
        card = existing.get(student.id)
        if card is not None and card.status == ReportCardStatus.PUBLISHED:
            skipped += 1  # un bulletin publié est figé : jamais écrasé
            continue
        snapshot = _build_snapshot(
            db, tenant=tenant, school_class=school_class, student=student, results=results,
            subject_ids=subject_ids, term=term, year=year, signers=signers, today=today,
        )
        if card is None:
            db.add(ReportCard(
                tenant_id=tenant_id, student_id=student.id, class_id=class_id, term=term, academic_year=year,
                status=ReportCardStatus.DRAFT, snapshot=snapshot, generated_at=_now(),
            ))
            created += 1
        else:
            card.class_id = class_id
            card.snapshot = snapshot
            card.generated_at = _now()
            updated += 1

    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="report_card.generated",
        target_type="SchoolClass", target_id=str(class_id),
        metadata={"term": term, "academic_year": year, "created": created, "updated": updated, "skipped_published": skipped},
    )
    db.commit()
    return {"created": created, "updated": updated, "skipped_published": skipped}


# ---------------- Consultation ----------------

def _is_head_teacher(db: Session, tenant_id: uuid.UUID, class_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return db.execute(
        select(SchoolClass.id).where(
            SchoolClass.id == class_id, SchoolClass.tenant_id == tenant_id, SchoolClass.head_teacher_id == user_id
        )
    ).first() is not None


def _summary_fields(card: ReportCard) -> dict:
    snap = card.snapshot
    return {
        "id": card.id, "student_id": card.student_id, "student_name": snap["student"]["name"],
        "class_id": card.class_id, "class_name": snap["student"]["class_name"], "term": card.term,
        "academic_year": card.academic_year, "status": card.status,
        "general_average": snap["general"]["average"], "rank": snap["general"]["rank"],
        "class_size": snap["general"]["class_size"], "published_at": card.published_at,
    }


def to_summary(card: ReportCard) -> ReportCardSummaryOut:
    return ReportCardSummaryOut(**_summary_fields(card))


def to_detail(card: ReportCard) -> ReportCardOut:
    return ReportCardOut(
        **_summary_fields(card), snapshot=card.snapshot, principal_comment=card.principal_comment,
        council_decision=card.council_decision,
    )


def _can_see(db: Session, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, card: ReportCard) -> bool:
    if actor_role in CAN_MANAGE_BULLETINS:
        return True
    if actor_role == UserRole.STAFF:
        return card.status == ReportCardStatus.PUBLISHED
    if actor_role == UserRole.TEACHER:
        return _is_head_teacher(db, tenant_id, card.class_id, actor_id)
    return False


def list_report_cards(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole,
    class_id: uuid.UUID | None = None, term: str | None = None, student_id: uuid.UUID | None = None,
) -> list[ReportCard]:
    query = select(ReportCard).where(ReportCard.tenant_id == tenant_id)
    if class_id:
        query = query.where(ReportCard.class_id == class_id)
    if term:
        query = query.where(ReportCard.term == term)
    if student_id:
        query = query.where(ReportCard.student_id == student_id)
    if actor_role == UserRole.STAFF:
        query = query.where(ReportCard.status == ReportCardStatus.PUBLISHED)
    elif actor_role == UserRole.TEACHER:
        query = query.where(
            ReportCard.class_id.in_(
                select(SchoolClass.id).where(SchoolClass.tenant_id == tenant_id, SchoolClass.head_teacher_id == actor_id)
            )
        )
    cards = list(db.execute(query).scalars().all())
    return sorted(cards, key=lambda c: (c.snapshot["student"]["name"].lower()))


def get_report_card(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, card_id: uuid.UUID,
) -> ReportCard:
    card = db.execute(
        select(ReportCard).where(ReportCard.id == card_id, ReportCard.tenant_id == tenant_id)
    ).scalar_one_or_none()
    # 404 (jamais 403) : ne pas révéler l'existence d'un bulletin qu'on n'a pas le droit de voir.
    if card is None or not _can_see(db, tenant_id, actor_id, actor_role, card):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulletin introuvable.")
    return card


# ---------------- Modification, publication ----------------

def update_remarks(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, card_id: uuid.UUID,
    data: RemarksUpdate,
) -> ReportCard:
    card = get_report_card(db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role, card_id=card_id)
    is_manager = actor_role in CAN_MANAGE_BULLETINS
    if not is_manager and not (actor_role == UserRole.TEACHER and _is_head_teacher(db, tenant_id, card.class_id, actor_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissions insuffisantes pour cette action.")
    if card.status == ReportCardStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce bulletin est publié : dépubliez-le pour le modifier.")
    fields = data.model_fields_set
    # La décision du conseil de classe relève de la direction/du censeur ;
    # le professeur principal rédige l'appréciation générale.
    if "council_decision" in fields and not is_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La décision du conseil de classe est réservée à la direction et au censeur.")
    if "principal_comment" in fields:
        card.principal_comment = data.principal_comment
    if "council_decision" in fields:
        card.council_decision = data.council_decision
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="report_card.remarks_updated",
        target_type="ReportCard", target_id=str(card.id), metadata={"fields": sorted(fields)},
    )
    db.commit()
    db.refresh(card)
    return card


def _refresh_snapshot(db: Session, tenant: Tenant, card: ReportCard) -> None:
    school_class = _get_class_or_404(db, tenant.id, card.class_id)
    student = db.get(Student, card.student_id)
    results = compute_class_term_results(db, tenant_id=tenant.id, class_id=card.class_id, term=card.term)
    card.snapshot = _build_snapshot(
        db, tenant=tenant, school_class=school_class, student=student, results=results,
        subject_ids=_class_subject_ids(db, tenant.id, card.class_id, results), term=card.term,
        year=card.academic_year, signers=_resolve_signers(db, tenant, school_class), today=date.today(),
    )
    card.generated_at = _now()


def publish_report_card(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, card_id: uuid.UUID) -> ReportCard:
    card = db.execute(
        select(ReportCard).where(ReportCard.id == card_id, ReportCard.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulletin introuvable.")
    if card.status == ReportCardStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce bulletin est déjà publié.")

    tenant = db.get(Tenant, tenant_id)
    _refresh_snapshot(db, tenant, card)  # jamais de chiffres périmés au moment de publier
    if card.snapshot["general"]["average"] is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Aucune note pour cette période : impossible de publier.")
    unlocked = db.execute(
        select(func.count()).select_from(Grade).where(
            Grade.tenant_id == tenant_id, Grade.student_id == card.student_id, Grade.term == card.term,
            Grade.is_locked.is_(False),
        )
    ).scalar_one()
    if unlocked:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{unlocked} note(s) de cette période ne sont pas encore verrouillées : validez les notes avant de publier.",
        )
    _freeze(db, tenant, card)  # identité, réglages et images : le bulletin se réimprimera à l'identique
    card.status = ReportCardStatus.PUBLISHED
    card.published_at = _now()
    card.published_by = actor_id
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="report_card.published",
        target_type="ReportCard", target_id=str(card.id),
        metadata={"student_id": str(card.student_id), "term": card.term, "frozen": True},
    )
    db.commit()
    db.refresh(card)
    return card


def unpublish_report_card(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, card_id: uuid.UUID) -> ReportCard:
    card = db.execute(
        select(ReportCard).where(ReportCard.id == card_id, ReportCard.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulletin introuvable.")
    if card.status != ReportCardStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce bulletin n'est pas publié.")
    card.status = ReportCardStatus.DRAFT
    card.published_at = None
    card.published_by = None
    card.frozen = None  # redevient un brouillon : identité et images seront relues à la prochaine publication
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="report_card.unpublished",
        target_type="ReportCard", target_id=str(card.id), metadata={"student_id": str(card.student_id), "term": card.term},
    )
    db.commit()
    db.refresh(card)
    return card


# ---------------- Parents ----------------

def list_report_cards_for_child(
    db: Session, *, tenant_id: uuid.UUID, parent_user_id: uuid.UUID, student_id: uuid.UUID,
) -> list[ReportCard]:
    assert_parent_linked_to_student(db, tenant_id=tenant_id, parent_user_id=parent_user_id, student_id=student_id)
    return list(
        db.execute(
            select(ReportCard).where(
                ReportCard.tenant_id == tenant_id, ReportCard.student_id == student_id,
                ReportCard.status == ReportCardStatus.PUBLISHED,
            ).order_by(ReportCard.academic_year.desc(), ReportCard.term.desc())
        ).scalars().all()
    )


def get_report_card_for_child(
    db: Session, *, tenant_id: uuid.UUID, parent_user_id: uuid.UUID, student_id: uuid.UUID, card_id: uuid.UUID,
) -> ReportCard:
    assert_parent_linked_to_student(db, tenant_id=tenant_id, parent_user_id=parent_user_id, student_id=student_id)
    card = db.execute(
        select(ReportCard).where(
            ReportCard.id == card_id, ReportCard.tenant_id == tenant_id, ReportCard.student_id == student_id,
            ReportCard.status == ReportCardStatus.PUBLISHED,
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bulletin introuvable.")
    return card


# ---------------- Appréciations de matière ----------------

def upsert_appreciation(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, actor_role: UserRole, data: AppreciationUpsert,
) -> SubjectAppreciation | None:
    student = db.execute(
        select(Student).where(Student.id == data.student_id, Student.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Élève introuvable.")
    subject = db.execute(
        select(Subject).where(Subject.id == data.subject_id, Subject.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matière introuvable.")
    if student.class_id is not None:
        check_assignment_restriction(
            db, tenant_id=tenant_id, teacher_id=actor_id, actor_role=actor_role,
            class_id=student.class_id, subject_id=data.subject_id,
        )
    existing = db.execute(
        select(SubjectAppreciation).where(
            SubjectAppreciation.student_id == data.student_id, SubjectAppreciation.subject_id == data.subject_id,
            SubjectAppreciation.term == data.term,
        )
    ).scalar_one_or_none()
    if not data.text:  # texte vide = effacer l'appréciation
        if existing is not None:
            db.delete(existing)
            db.commit()
        return None
    if existing is None:
        existing = SubjectAppreciation(
            tenant_id=tenant_id, student_id=data.student_id, subject_id=data.subject_id, term=data.term,
            teacher_id=actor_id, text=data.text,
        )
        db.add(existing)
    else:
        existing.text = data.text
        existing.teacher_id = actor_id
    db.commit()
    db.refresh(existing)
    return existing


def list_appreciations(
    db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, subject_id: uuid.UUID, term: str,
) -> list[SubjectAppreciation]:
    return list(
        db.execute(
            select(SubjectAppreciation).where(
                SubjectAppreciation.tenant_id == tenant_id, SubjectAppreciation.subject_id == subject_id,
                SubjectAppreciation.term == term,
                SubjectAppreciation.student_id.in_(select(Student.id).where(Student.tenant_id == tenant_id, Student.class_id == class_id)),
            )
        ).scalars().all()
    )


# ---------------- PDF ----------------

def _live_render_inputs(db: Session, tenant: Tenant, card: ReportCard) -> tuple[dict, dict]:
    """Réglages d'affichage et images tels qu'ils sont MAINTENANT."""
    signers = card.snapshot.get("signers", {})

    def user_images(key: str) -> tuple[str | None, str | None]:
        ref = signers.get(key)
        if not ref:
            return None, None
        user = db.execute(
            select(User).where(User.id == uuid.UUID(ref["user_id"]), User.tenant_id == tenant.id)
        ).scalar_one_or_none()
        return (user.signature_base64, user.stamp_base64) if user else (None, None)

    director_sig, director_stamp = user_images("director")
    censor_sig, censor_stamp = user_images("censor")
    head_sig, head_stamp = user_images("head_teacher")
    settings = {
        "name": tenant.name, "trade_name": tenant.trade_name, "address": tenant.address, "rccm": tenant.rccm,
        "ifu": tenant.ifu, "motto": tenant.bulletin_motto, "authority_header": tenant.bulletin_authority_header,
        "place": tenant.bulletin_place, "show_appreciations": tenant.bulletin_show_appreciations,
        "show_school_life": tenant.bulletin_show_school_life,
        "show_head_teacher_signature": tenant.bulletin_show_head_teacher_signature,
    }
    images = {
        "logo": tenant.logo_base64, "director_signature": director_sig, "director_stamp": director_stamp,
        "censor_signature": censor_sig, "censor_stamp": censor_stamp, "head_signature": head_sig, "head_stamp": head_stamp,
    }
    return settings, images


def _freeze(db: Session, tenant: Tenant, card: ReportCard) -> None:
    """Fige identité, réglages d'affichage et images au moment de la
    publication. Les images sont rangées par empreinte dans ReportCardAsset
    (une seule copie par image et par établissement)."""
    settings, images = _live_render_inputs(db, tenant, card)
    hashes: dict[str, str | None] = {}
    for key, data_uri in images.items():
        if not data_uri:
            hashes[key] = None
            continue
        digest = hashlib.sha256(data_uri.encode("utf-8")).hexdigest()
        db.execute(
            pg_insert(ReportCardAsset)
            .values(id=uuid.uuid4(), tenant_id=tenant.id, sha256=digest, data_uri=data_uri, created_at=_now(), updated_at=_now())
            .on_conflict_do_nothing(constraint="uq_report_card_asset")
        )
        hashes[key] = digest
    card.frozen = {"settings": settings, "images": hashes}


def _frozen_render_inputs(db: Session, tenant_id: uuid.UUID, card: ReportCard) -> tuple[dict, dict]:
    frozen = card.frozen
    wanted = {h for h in frozen["images"].values() if h}
    assets = {}
    if wanted:
        assets = {
            a.sha256: a.data_uri
            for a in db.execute(
                select(ReportCardAsset).where(ReportCardAsset.tenant_id == tenant_id, ReportCardAsset.sha256.in_(wanted))
            ).scalars().all()
        }
    return frozen["settings"], {key: (assets.get(h) if h else None) for key, h in frozen["images"].items()}


def render_report_card_pdf(db: Session, *, tenant_id: uuid.UUID, card: ReportCard) -> bytes:
    """Produit le PDF. Un bulletin PUBLIÉ est rendu depuis ses données figées
    (chiffres, identité, réglages, images) : il est identique à chaque
    impression. Un brouillon utilise l'état courant de l'établissement."""
    published = card.status == ReportCardStatus.PUBLISHED
    if published and card.frozen:
        settings, images = _frozen_render_inputs(db, tenant_id, card)
    else:
        settings, images = _live_render_inputs(db, db.get(Tenant, tenant_id), card)
    return build_report_card_pdf(
        snapshot=card.snapshot, settings=settings, images=images, principal_comment=card.principal_comment,
        council_decision=card.council_decision, is_published=published,
        issued_on=(card.published_at or _now()).date(),
    )
