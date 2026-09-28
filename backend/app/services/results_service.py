"""Calcul des résultats scolaires — source unique pour la moyenne d'un élève
(fiche élève, portail parent, rapports) ET pour les bulletins.

Règles (celles d'un bulletin officiel) :
  * moyenne de matière  = Σ(note × coefficient de l'évaluation) / Σ(coefficients
    des évaluations) — arrondie à 2 décimales ;
  * moyenne générale    = Σ(moyenne de matière × coefficient DE LA MATIÈRE) /
    Σ(coefficients des matières comptées) — seules les matières ayant au moins
    une note pour l'élève sont comptées ;
  * rang                = classement décroissant par moyenne générale, les
    ex æquo partagent le même rang (1, 2, 2, 4) ;
  * moyenne de classe   = moyenne des moyennes des élèves de la classe qui en
    ont une.
"""
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Hashable, Iterable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import Subject
from app.models.grade import Grade
from app.models.student import Student, StudentStatus

K = TypeVar("K", bound=Hashable)


def weighted_subject_average(grades: Iterable[Grade]) -> float | None:
    weighted = 0.0
    total = 0.0
    for g in grades:
        weighted += float(g.value) * float(g.coefficient)
        total += float(g.coefficient)
    return round(weighted / total, 2) if total else None


def weighted_general_average(subject_averages: dict[uuid.UUID, float], coefficients: dict[uuid.UUID, float]) -> float | None:
    weighted = 0.0
    total = 0.0
    for subject_id, avg in subject_averages.items():
        coef = coefficients.get(subject_id, 0.0)
        if coef <= 0:
            continue
        weighted += avg * coef
        total += coef
    return round(weighted / total, 2) if total else None


def competition_ranks(values: dict[K, float]) -> dict[K, int]:
    """Rang « olympique » : décroissant, ex æquo au même rang, rang suivant sauté."""
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    ranks: dict[K, int] = {}
    previous: float | None = None
    previous_rank = 0
    for position, (key, value) in enumerate(ordered, start=1):
        rank = previous_rank if previous is not None and value == previous else position
        ranks[key] = rank
        previous, previous_rank = value, rank
    return ranks


def subject_coefficients(db: Session, tenant_id: uuid.UUID) -> dict[uuid.UUID, float]:
    rows = db.execute(select(Subject).where(Subject.tenant_id == tenant_id)).scalars().all()
    return {s.id: float(s.default_coefficient) for s in rows}


@dataclass
class ClassTermResults:
    student_ids: list[uuid.UUID]
    subject_names: dict[uuid.UUID, str]
    coefficients: dict[uuid.UUID, float]
    subject_averages: dict[uuid.UUID, dict[uuid.UUID, float]] = field(default_factory=dict)  # élève -> matière -> moyenne
    general_averages: dict[uuid.UUID, float] = field(default_factory=dict)                   # élève -> moyenne générale
    general_ranks: dict[uuid.UUID, int] = field(default_factory=dict)
    subject_class_average: dict[uuid.UUID, float] = field(default_factory=dict)              # matière -> moyenne de classe
    subject_ranks: dict[uuid.UUID, dict[uuid.UUID, int]] = field(default_factory=dict)       # matière -> élève -> rang
    class_average: float | None = None


def compute_class_term_results(db: Session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, term: str) -> ClassTermResults:
    student_ids = list(
        db.execute(
            select(Student.id).where(
                Student.tenant_id == tenant_id, Student.class_id == class_id, Student.status == StudentStatus.ACTIVE
            )
        ).scalars().all()
    )
    subjects = db.execute(select(Subject).where(Subject.tenant_id == tenant_id)).scalars().all()
    results = ClassTermResults(
        student_ids=student_ids,
        subject_names={s.id: s.name for s in subjects},
        coefficients={s.id: float(s.default_coefficient) for s in subjects},
    )
    if not student_ids:
        return results

    grades = db.execute(
        select(Grade).where(Grade.tenant_id == tenant_id, Grade.term == term, Grade.student_id.in_(student_ids))
    ).scalars().all()
    per_student_subject: dict[uuid.UUID, dict[uuid.UUID, list[Grade]]] = defaultdict(lambda: defaultdict(list))
    for g in grades:
        per_student_subject[g.student_id][g.subject_id].append(g)

    for sid in student_ids:
        averages: dict[uuid.UUID, float] = {}
        for subject_id, subject_grades in per_student_subject.get(sid, {}).items():
            avg = weighted_subject_average(subject_grades)
            if avg is not None:
                averages[subject_id] = avg
        results.subject_averages[sid] = averages
        general = weighted_general_average(averages, results.coefficients)
        if general is not None:
            results.general_averages[sid] = general

    results.general_ranks = competition_ranks(results.general_averages)
    if results.general_averages:
        results.class_average = round(sum(results.general_averages.values()) / len(results.general_averages), 2)

    by_subject: dict[uuid.UUID, dict[uuid.UUID, float]] = defaultdict(dict)
    for sid, averages in results.subject_averages.items():
        for subject_id, avg in averages.items():
            by_subject[subject_id][sid] = avg
    for subject_id, per_student in by_subject.items():
        results.subject_class_average[subject_id] = round(sum(per_student.values()) / len(per_student), 2)
        results.subject_ranks[subject_id] = competition_ranks(per_student)
    return results
