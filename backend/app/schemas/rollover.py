import uuid

from pydantic import BaseModel, Field


class ClassMove(BaseModel):
    from_class_id: uuid.UUID
    # None = la classe termine son cursus (ses élèves passent au statut « diplômé »).
    to_class_id: uuid.UUID | None = None


class RolloverRequest(BaseModel):
    # Année que la Direction croit clôturer : protège contre un écran périmé
    # et contre le double envoi (le 2e envoi voit une année déjà changée → 409).
    from_year: str = Field(pattern=r"^\d{4}-\d{4}$")
    to_year: str = Field(pattern=r"^\d{4}-\d{4}$")
    class_moves: list[ClassMove] = Field(max_length=300)
    # Élèves qui redoublent : ils restent dans leur classe actuelle.
    repeater_student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)


class RolloverClassRow(BaseModel):
    from_class_id: uuid.UUID
    from_class: str
    to_class: str | None
    promoted: int
    repeated: int
    graduated: int


class RolloverReport(BaseModel):
    dry_run: bool
    executed: bool
    from_year: str
    to_year: str
    promoted: int
    repeated: int
    graduated: int
    without_class: int
    classes: list[RolloverClassRow]
    errors: list[str]
    warnings: list[str]


class AtRiskStudent(BaseModel):
    id: uuid.UUID
    name: str
    annual_average: float


class ProposalClass(BaseModel):
    id: uuid.UUID
    name: str
    level: str
    active_count: int
    suggested_to_class_id: uuid.UUID | None
    suggested_graduate: bool
    without_average: int
    at_risk: list[AtRiskStudent]


class RolloverProposal(BaseModel):
    current_year: str
    next_year: str
    pass_mark: float
    classes: list[ProposalClass]
    targets: list[dict]


class EnrollmentOut(BaseModel):
    academic_year: str
    class_name: str
    outcome: str
    next_class_name: str | None
