"""Passage d'année scolaire (AU-07).

Principes :

* **Le plan est validé en entier avant la moindre écriture.** Aperçu (dry_run,
  par défaut) et exécution partagent le même code : ce qui a été prévisualisé
  est exactement ce qui s'exécute.
* **« Rien d'oublié » :** toute classe ayant des élèves actifs doit avoir une
  destination (ou être déclarée terminale). Sinon le plan est refusé en
  nommant les classes manquantes.
* **Atomique et non rejouable :** l'établissement est verrouillé (SELECT … FOR
  UPDATE) ; l'année source est revérifiée sous verrou. Un double clic, un
  nouvel essai après coupure réseau ou deux directeurs simultanés ne peuvent
  pas passer l'année deux fois : le second reçoit un 409.
* **Mouvements simultanés :** les listes d'élèves sont figées AVANT toute
  modification, donc 6e→5e et 5e→4e dans le même plan ne font pas « monter »
  un élève de deux classes.
* **Traçable :** une ligne d'historique par élève (classe de l'année clôturée,
  issue, classe suivante) et une entrée d'audit globale.
* Ne touche NI aux notes (elles portent leur année), NI aux bulletins publiés,
  NI aux affectations d'enseignants et emplois du temps (rattachés aux classes,
  qui subsistent d'une année à l'autre).
"""
import re
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass
from app.models.enrollment import EnrollmentOutcome, StudentEnrollment
from app.models.grade import Grade
from app.models.report_card import ReportCard, ReportCardStatus
from app.models.student import Student, StudentStatus
from app.models.tenant import Tenant
from app.schemas.rollover import RolloverReport, RolloverRequest
from app.services.academic_year_service import current_year, ensure_academic_year, is_valid_year, next_year
from app.services.audit_service import log_action
from app.services.finance_service import finance_totals
from app.services.results_service import compute_class_term_results

TERMS = ("T1", "T2", "T3")
DEFAULT_PASS_MARK = 10.0
MAX_LISTED_NAMES = 8

# Ordre des niveaux (système béninois). Sert UNIQUEMENT à proposer une
# destination par défaut ; la Direction valide ou corrige chaque ligne.
LEVEL_ORDER = ["ci", "cp", "ce1", "ce2", "cm1", "cm2", "6e", "5e", "4e", "3e", "2nde", "1ere", "tle"]
TERMINAL_LEVEL = "tle"


def normalize_level(level: str) -> str | None:
    text = unicodedata.normalize("NFKD", level or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[\s.\-_]", "", text)
    if text in LEVEL_ORDER:
        return text
    m = re.fullmatch(r"([3-6])(e|eme|ieme)", text)
    if m:
        return f"{m.group(1)}e"
    if text in ("2nde", "2nd", "seconde", "2de"):
        return "2nde"
    if text in ("1ere", "1re", "premiere", "1ere"):
        return "1ere"
    if text in ("tle", "terminale", "terminal"):
        return "tle"
    return None


def _suffix(name: str) -> str:
    parts = (name or "").strip().split()
    return parts[-1].lower() if len(parts) > 1 else ""


def suggest_destination(source: SchoolClass, classes: list[SchoolClass]) -> tuple[uuid.UUID | None, bool]:
    """(classe de destination suggérée, la classe est-elle terminale ?)."""
    level = normalize_level(source.level)
    if level is None:
        return None, False
    if level == TERMINAL_LEVEL:
        return None, True
    nxt = LEVEL_ORDER[LEVEL_ORDER.index(level) + 1]
    candidates = [c for c in classes if c.id != source.id and normalize_level(c.level) == nxt]
    if len(candidates) == 1:
        return candidates[0].id, False
    same = [c for c in candidates if _suffix(c.name) == _suffix(source.name) and _suffix(c.name)]
    return (same[0].id if len(same) == 1 else None), False


# ---------------- Proposition ----------------

def build_proposal(db: Session, *, tenant_id: uuid.UUID, pass_mark: float = DEFAULT_PASS_MARK) -> dict:
    year = current_year(db, tenant_id)
    classes = list(db.execute(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id).order_by(SchoolClass.name)).scalars())
    counts = dict(
        db.execute(
            select(Student.class_id, func.count()).where(
                Student.tenant_id == tenant_id, Student.status == StudentStatus.ACTIVE, Student.class_id.is_not(None)
            ).group_by(Student.class_id)
        ).all()
    )
    names = {
        sid: f"{first} {last}".strip()
        for sid, first, last in db.execute(
            select(Student.id, Student.first_name, Student.last_name).where(Student.tenant_id == tenant_id)
        ).all()
    }
    rows = []
    for c in classes:
        active = int(counts.get(c.id, 0))
        if active == 0:
            continue
        per_term: dict[uuid.UUID, list[float]] = defaultdict(list)
        student_ids: list[uuid.UUID] = []
        for term in TERMS:
            res = compute_class_term_results(db, tenant_id=tenant_id, class_id=c.id, term=term, academic_year=year)
            student_ids = res.student_ids
            for sid, avg in res.general_averages.items():
                per_term[sid].append(avg)
        at_risk = []
        for sid, values in per_term.items():
            annual = round(sum(values) / len(values), 2)
            if annual < pass_mark:
                at_risk.append({"id": sid, "name": names.get(sid, ""), "annual_average": annual})
        at_risk.sort(key=lambda r: (r["annual_average"], r["name"]))
        dest, terminal = suggest_destination(c, classes)
        rows.append({
            "id": c.id, "name": c.name, "level": c.level, "active_count": active,
            "suggested_to_class_id": dest, "suggested_graduate": terminal,
            "without_average": len(student_ids) - len(per_term), "at_risk": at_risk,
        })
    return {
        "current_year": year, "next_year": next_year(year), "pass_mark": pass_mark,
        "classes": rows, "targets": [{"id": c.id, "name": c.name, "level": c.level} for c in classes],
    }


# ---------------- Plan ----------------

@dataclass
class _Plan:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # classe source -> {"to": SchoolClass|None, "promoted": [ids], "repeated": [ids], "graduated": [ids]}
    moves: dict[uuid.UUID, dict] = field(default_factory=dict)
    classes: dict[uuid.UUID, SchoolClass] = field(default_factory=dict)
    without_class: int = 0


def _names(items: list[str]) -> str:
    shown = ", ".join(items[:MAX_LISTED_NAMES])
    return shown + (f" et {len(items) - MAX_LISTED_NAMES} autre(s)" if len(items) > MAX_LISTED_NAMES else "")


def _build_plan(db: Session, *, tenant_id: uuid.UUID, req: RolloverRequest, year: str) -> _Plan:
    plan = _Plan()
    if req.from_year != year:
        # Géré par l'appelant (409) ; ici on ne planifie pas sur une base périmée.
        plan.errors.append(f"L'année en cours est {year}, pas {req.from_year}.")
        return plan
    if not is_valid_year(req.from_year) or not is_valid_year(req.to_year) or req.to_year != next_year(req.from_year):
        plan.errors.append(f"La nouvelle année doit être {next_year(year)} (l'année qui suit {year}).")

    plan.classes = {c.id: c for c in db.execute(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id)).scalars()}

    seen: set[uuid.UUID] = set()
    for mv in req.class_moves:
        if mv.from_class_id in seen:
            plan.errors.append(f"La classe « {plan.classes[mv.from_class_id].name} » apparaît deux fois dans le plan." if mv.from_class_id in plan.classes else "Une classe apparaît deux fois dans le plan.")
            continue
        seen.add(mv.from_class_id)
        if mv.from_class_id not in plan.classes:
            plan.errors.append("Une classe du plan n'existe pas dans cet établissement.")
            continue
        if mv.to_class_id is not None and mv.to_class_id not in plan.classes:
            plan.errors.append(f"La classe de destination de « {plan.classes[mv.from_class_id].name} » n'existe pas.")
            continue
        if mv.to_class_id == mv.from_class_id:
            plan.errors.append(
                f"« {plan.classes[mv.from_class_id].name} » ne peut pas être sa propre destination : "
                "cochez les élèves concernés comme redoublants."
            )
            continue
        plan.moves[mv.from_class_id] = {
            "to": plan.classes.get(mv.to_class_id) if mv.to_class_id else None,
            "promoted": [], "repeated": [], "graduated": [],
        }

    active = db.execute(
        select(Student.id, Student.class_id, Student.first_name, Student.last_name).where(
            Student.tenant_id == tenant_id, Student.status == StudentStatus.ACTIVE
        )
    ).all()
    plan.without_class = sum(1 for r in active if r.class_id is None)
    by_class: dict[uuid.UUID, list] = defaultdict(list)
    for r in active:
        if r.class_id is not None:
            by_class[r.class_id].append(r)

    forgotten = [plan.classes[cid].name for cid in by_class if cid not in plan.moves and cid in plan.classes]
    if forgotten:
        plan.errors.append(f"Classe(s) avec des élèves actifs sans destination : {_names(sorted(forgotten))}.")

    repeaters = set(req.repeater_student_ids)
    known = {r.id: r for rows in by_class.values() for r in rows if r.class_id in plan.moves}
    unknown = repeaters - set(known)
    if unknown:
        plan.errors.append(
            f"{len(unknown)} redoublant(s) indiqué(s) ne sont pas des élèves actifs d'une classe du plan."
        )

    for cid, move in plan.moves.items():
        for r in by_class.get(cid, []):
            if r.id in repeaters:
                move["repeated"].append(r.id)
            elif move["to"] is None:
                move["graduated"].append(r.id)
            else:
                move["promoted"].append(r.id)

    # Avertissements (n'empêchent pas l'exécution).
    unlocked = db.execute(
        select(func.count()).select_from(Grade).where(
            Grade.tenant_id == tenant_id, Grade.academic_year == year, Grade.is_locked.is_(False)
        )
    ).scalar_one()
    if unlocked:
        plan.warnings.append(
            f"{unlocked} note(s) de {year} ne sont pas verrouillées. Après le passage d'année, seule la Direction "
            "pourra les corriger (avec traçabilité)."
        )
    drafts = db.execute(
        select(func.count()).select_from(ReportCard).where(
            ReportCard.tenant_id == tenant_id, ReportCard.academic_year == year,
            ReportCard.status == ReportCardStatus.DRAFT,
        )
    ).scalar_one()
    if drafts:
        plan.warnings.append(
            f"{drafts} bulletin(s) de {year} sont encore en brouillon : ils ne seront plus régénérables après le passage d'année."
        )
    owed = finance_totals(db, tenant_id=tenant_id, year=year)["outstanding"]
    if owed > 0:
        plan.warnings.append(
            f"{owed:,.0f} F restent dus sur les factures de {year} : ils deviendront des « arriérés » "
            "(toujours encaissables, suivis séparément dans les Rapports).".replace(",", " ")
        )
    targets: dict[uuid.UUID, list[str]] = defaultdict(list)
    for cid, move in plan.moves.items():
        if move["to"] is not None:
            targets[move["to"].id].append(plan.classes[cid].name)
    for tid, sources in targets.items():
        if len(sources) > 1:
            plan.warnings.append(f"Les classes {_names(sources)} sont regroupées dans « {plan.classes[tid].name} ».")
    if plan.without_class:
        plan.warnings.append(f"{plan.without_class} élève(s) actif(s) sans classe ne sont pas concernés par le plan.")
    tenant = db.get(Tenant, tenant_id)
    if tenant.term_periods:
        plan.warnings.append("Les dates des trimestres seront réinitialisées : pensez à saisir celles de la nouvelle année.")
    return plan


def _report(plan: _Plan, req: RolloverRequest, *, dry_run: bool, executed: bool) -> RolloverReport:
    rows = [
        {
            "from_class_id": cid, "from_class": plan.classes[cid].name, "to_class": m["to"].name if m["to"] else None,
            "promoted": len(m["promoted"]), "repeated": len(m["repeated"]), "graduated": len(m["graduated"]),
        }
        for cid, m in plan.moves.items()
    ]
    rows.sort(key=lambda r: r["from_class"])
    return RolloverReport(
        dry_run=dry_run, executed=executed, from_year=req.from_year, to_year=req.to_year,
        promoted=sum(r["promoted"] for r in rows), repeated=sum(r["repeated"] for r in rows),
        graduated=sum(r["graduated"] for r in rows), without_class=plan.without_class,
        classes=rows, errors=plan.errors, warnings=plan.warnings,
    )


# ---------------- Exécution ----------------

def run_rollover(
    db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, req: RolloverRequest, commit: bool,
) -> RolloverReport:
    if not commit:
        year = current_year(db, tenant_id)
        plan = _build_plan(db, tenant_id=tenant_id, req=req, year=year)
        return _report(plan, req, dry_run=True, executed=False)

    # Verrou d'établissement : sérialise deux passages simultanés. populate_existing
    # force la relecture de l'année sous verrou (le 2e arrivé voit l'année déjà changée).
    tenant = db.execute(
        select(Tenant).where(Tenant.id == tenant_id).with_for_update().execution_options(populate_existing=True)
    ).scalar_one()
    year = tenant.academic_year or ensure_academic_year(db, tenant_id)
    if req.from_year != year:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"L'année en cours est {year} : le passage d'année demandé ({req.from_year} → {req.to_year}) "
                   "n'est plus applicable. Rechargez la page.",
        )
    plan = _build_plan(db, tenant_id=tenant_id, req=req, year=year)
    if plan.errors:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Passage d'année refusé ({len(plan.errors)} erreur(s)) : " + " ".join(plan.errors),
        )

    history: list[dict] = []
    for cid, move in plan.moves.items():
        src = plan.classes[cid]
        to_name = move["to"].name if move["to"] else None
        for key, outcome in (("promoted", EnrollmentOutcome.PROMOTED), ("repeated", EnrollmentOutcome.REPEATED),
                             ("graduated", EnrollmentOutcome.GRADUATED)):
            ids = move[key]
            if not ids:
                continue
            for sid in ids:
                history.append({
                    "tenant_id": tenant_id, "student_id": sid, "academic_year": year, "class_id": cid,
                    "class_name": src.name, "outcome": outcome,
                    "next_class_name": src.name if outcome == EnrollmentOutcome.REPEATED else to_name,
                })
            if key == "promoted":
                db.execute(update(Student).where(Student.id.in_(ids), Student.tenant_id == tenant_id).values(
                    class_id=move["to"].id, is_repeater=False))
            elif key == "repeated":
                db.execute(update(Student).where(Student.id.in_(ids), Student.tenant_id == tenant_id).values(is_repeater=True))
            else:
                db.execute(update(Student).where(Student.id.in_(ids), Student.tenant_id == tenant_id).values(
                    status=StudentStatus.GRADUATED, is_repeater=False))
    if history:
        db.execute(insert(StudentEnrollment), history)

    previous_periods = tenant.term_periods
    tenant.academic_year = req.to_year
    tenant.term_periods = None

    report = _report(plan, req, dry_run=False, executed=True)
    log_action(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="academic_year.rolled_over",
        target_type="Tenant", target_id=str(tenant_id),
        metadata={
            "from_year": year, "to_year": req.to_year, "promoted": report.promoted, "repeated": report.repeated,
            "graduated": report.graduated,
            "classes": [{"from": r["from_class"], "to": r["to_class"], "promoted": r["promoted"],
                         "repeated": r["repeated"], "graduated": r["graduated"]} for r in report.model_dump()["classes"]],
            "previous_term_periods": previous_periods,
        },
    )
    db.commit()
    return report
