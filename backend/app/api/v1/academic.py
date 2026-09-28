import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_REGISTRY, CAN_MANAGE_TEACHING, CAN_READ_REGISTRY
from app.schemas.academic import (
    SchoolClassCreate, SchoolClassOut, SchoolClassUpdate, StudentCreate, StudentOut, StudentUpdate, SubjectCreate, SubjectOut, SubjectUpdate,
)
from app.services.academic_service import (
    create_class, create_student, create_subject, get_student_or_404, list_classes, list_students, list_subjects,
    update_class, update_student, update_subject,
)

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
    db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_READ_REGISTRY)),
) -> list[StudentOut]:
    return list_students(db, tenant_id=current_user.tenant_id)


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
