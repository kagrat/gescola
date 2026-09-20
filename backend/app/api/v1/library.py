import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_tenant_db, require_roles
from app.core.roles import CAN_MANAGE_REGISTRY
from app.schemas.library import BookCreate, BookOut, LoanCreate, LoanOut
from app.services.library_service import create_book, create_loan, list_books, list_loans_for_student, return_loan

router = APIRouter(prefix="/library", tags=["library"])


@router.post("/books", response_model=BookOut, status_code=201)
def create_book_endpoint(
    payload: BookCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> BookOut:
    return create_book(db, tenant_id=current_user.tenant_id, data=payload)


@router.get("/books", response_model=list[BookOut])
def list_books_endpoint(
    db: Session = Depends(get_tenant_db), current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> list[BookOut]:
    return list_books(db, tenant_id=current_user.tenant_id)


@router.post("/loans", response_model=LoanOut, status_code=201)
def create_loan_endpoint(
    payload: LoanCreate, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> LoanOut:
    return create_loan(db, tenant_id=current_user.tenant_id, actor_id=current_user.id, data=payload)


@router.post("/loans/{loan_id}/return", response_model=LoanOut)
def return_loan_endpoint(
    loan_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> LoanOut:
    return return_loan(db, tenant_id=current_user.tenant_id, loan_id=loan_id)


@router.get("/students/{student_id}/loans", response_model=list[LoanOut])
def list_loans_endpoint(
    student_id: uuid.UUID, db: Session = Depends(get_tenant_db),
    current_user: CurrentUser = Depends(require_roles(*CAN_MANAGE_REGISTRY)),
) -> list[LoanOut]:
    return list_loans_for_student(db, tenant_id=current_user.tenant_id, student_id=student_id)
