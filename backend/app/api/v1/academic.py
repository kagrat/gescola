import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_REGISTRY, CAN_MANAGE_TEACHING, CAN_READ_REGISTRY
from app.models.student import StudentStatus
from app.schemas.academic import (
    SchoolClassCreate, SchoolClassOut, SchoolClassUpdate, StudentCreate, StudentImportReport, StudentOut, StudentStatusChange,
    StudentUpdate, SubjectCreate, SubjectOut, SubjectUpdate,
)
from app.services.academic_service import (
    create_class, create_student, create_subject, get_student_or_404, list_classes, list_subjects,
    update_class, update_student, update_subject,
)
from app.services.student_import_service import MAX_FILE_BYTES, process_import, template_csv
from app.services.student_service import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, change_student_status, search_students

router = APIRouter(tags=["academic"])

# --- Classes ---
@router.patch("/classes/{class_id}", response_model=SchoolClassOut)
def update_class_endpoint(
    class_id: uuid.UUID,
    payload: SchoolClassUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*set(CAN_MANAGE_REGISTRY + CAN_MANAGE_TEACHING))),
) -> SchoolClassOut:
    # Désigner le professeur principal est un acte de coordination
    # pédagogique (direction, censeur, fondateur) — pas du secrétariat, qui
    # peut en revanche corriger le nom/niveau/cycle d'une classe.
    if "head_teacher_id" in payload.model_fields_set and current_user.role not in CAN_MANAGE_TEACHING:
        raise HTTPException(status_code=403, detail="Permissions insuffisantes pour cette action.")
    return update_class(db, tenant_id=current_user.tenant_id, class_id=class_id, data=payload)


@router.post("/classes", response_model=SchoolClassOut, status_code=201)
def create_class_endpoint(
    payload: SchoolClassCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> SchoolClassOut:
    return create_class(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/classes", response_model=list[SchoolClassOut])
def list_classes_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[SchoolClassOut]:
    return list_classes(db, tenant_id=current_user.tenant_id)


# --- Subjects ---
@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject_endpoint(
    payload: SubjectCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> SubjectOut:
    return create_subject(db, tenant_id=current_user.tenant_id, data=payload)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject_endpoint(
    subject_id: uuid.UUID,
    payload: SubjectUpdate,
    db: Session = Depends(get_tenant_db),
    # Le coefficient d'une matière pilote la moyenne générale des bulletins :
    # décision pédagogique, donc ouverte aussi au censeur.
    current_user: CurrentUser = Depends(require_roles(*set(CAN_MANAGE_REGISTRY + CAN_MANAGE_TEACHING))),
) -> SubjectOut:
    return update_subject(db, tenant_id=current_user.tenant_id, subject_id=subject_id, data=payload)


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects_endpoint(
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[SubjectOut]:
    return list_subjects(db, tenant_id=current_user.tenant_id)


# --- Students ---
@router.post("/students", response_model=StudentOut, status_code=201)
def create_student_endpoint(
    payload: StudentCreate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> StudentOut:
    return create_student(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/students", response_model=list[StudentOut])
def list_students_endpoint(
    response: Response,
    q: str | None = Query(default=None, max_length=100, description="Prénom, nom ou matricule (plusieurs mots possibles)"),
    class_id: uuid.UUID | None = None,
    unassigned: bool = False,
    student_status: StudentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[StudentOut]:
    """Liste paginée. Le total correspondant aux filtres est dans l'en-tête
    X-Total-Count ; la réponse reste une simple liste (compatibilité)."""
    items, total = search_students(
        db, tenant_id=current_user.tenant_id, q=q, class_id=class_id, unassigned=unassigned,
        student_status=student_status, limit=limit, offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return items


@router.post("/students/{student_id}/status", response_model=StudentOut)
def change_student_status_endpoint(
    student_id: uuid.UUID,
    payload: StudentStatusChange,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> StudentOut:
    return change_student_status(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, student_id=student_id,
        new_status=payload.status, reason=payload.reason,
    )


@router.get("/students/import/template")
def student_import_template_endpoint(
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> Response:
    return Response(
        content=template_csv(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modele-import-eleves.csv"'},
    )


@router.post("/students/import", response_model=StudentImportReport)
def import_students_endpoint(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True, description="true = aperçu sans rien enregistrer (défaut) ; false = import réel"),
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> StudentImportReport:
    # On lit au plus MAX_FILE_BYTES + 1 octet : un fichier géant n'est jamais chargé en mémoire.
    content = file.file.read(MAX_FILE_BYTES + 1)
    report, imported = process_import(
        db, tenant_id=current_user.tenant_id, actor_id=current_user.id, content=content,
        filename=(file.filename or "import")[:200], commit=not dry_run,
    )
    return StudentImportReport(
        dry_run=dry_run, total_rows=report.total_rows, valid_rows=report.valid_rows, imported=imported,
        error_count=report.error_count, warning_count=report.warning_count,
        errors=[{"row": i.row, "message": i.message, "field": i.field} for i in report.errors],
        warnings=[{"row": i.row, "message": i.message, "field": i.field} for i in report.warnings],
        ignored_columns=report.ignored_columns, preview=report.preview,
    )


@router.get("/students/{student_id}", response_model=StudentOut)
def get_student_endpoint(
    student_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> StudentOut:
    return get_student_or_404(db, tenant_id=current_user.tenant_id, student_id=student_id)


@router.patch("/students/{student_id}", response_model=StudentOut)
def update_student_endpoint(
    student_id: uuid.UUID,
    payload: StudentUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> StudentOut:
    return update_student(db, tenant_id=current_user.tenant_id, student_id=student_id, data=payload)
