import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_REGISTRY, CAN_READ_REGISTRY
from app.schemas.academic import (
    SchoolClassCreate, SchoolClassOut, StudentCreate, StudentOut, StudentUpdate, SubjectCreate, SubjectOut,
)
from app.services.academic_service import (
    create_class, create_student, create_subject, get_student_or_404, list_classes, list_students, list_subjects,
    update_student,
)

router = APIRouter(tags=["academic"])

# --- Classes ---
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
