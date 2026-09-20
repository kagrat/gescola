import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library import Book, Loan
from app.schemas.library import BookCreate, LoanCreate
from app.services.academic_service import get_student_or_404
from app.services.audit_service import log_action


def create_book(db: Session, *, tenant_id: uuid.UUID, data: BookCreate) -> Book:
    book = Book(
        tenant_id=tenant_id, title=data.title, author=data.author, isbn=data.isbn,
        total_copies=data.total_copies, available_copies=data.total_copies,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def list_books(db: Session, *, tenant_id: uuid.UUID) -> list[Book]:
    return list(db.execute(select(Book).where(Book.tenant_id == tenant_id)).scalars().all())


def create_loan(db: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, data: LoanCreate) -> Loan:
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)

    book = db.execute(select(Book).where(Book.id == data.book_id, Book.tenant_id == tenant_id)).scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ouvrage introuvable.")
    if book.available_copies <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun exemplaire disponible actuellement.")

    book.available_copies -= 1
    loan = Loan(
        tenant_id=tenant_id, book_id=book.id, student_id=data.student_id,
        loaned_at=date.today(), due_at=data.due_at,
    )
    db.add(loan)
    log_action(db, tenant_id=tenant_id, actor_user_id=actor_id, action="library.loan_created",
               target_type="Loan", target_id=None, metadata={"book_id": str(book.id), "student_id": str(data.student_id)})
    db.commit()
    db.refresh(loan)
    return loan


def return_loan(db: Session, *, tenant_id: uuid.UUID, loan_id: uuid.UUID) -> Loan:
    loan = db.execute(select(Loan).where(Loan.id == loan_id, Loan.tenant_id == tenant_id)).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emprunt introuvable.")
    if loan.returned_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet emprunt est déjà clôturé.")

    loan.returned_at = date.today()
    book = db.get(Book, loan.book_id)
    if book is not None:
        book.available_copies = min(book.available_copies + 1, book.total_copies)
    db.commit()
    db.refresh(loan)
    return loan


def list_loans_for_student(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[Loan]:
    get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    return list(
        db.execute(select(Loan).where(Loan.tenant_id == tenant_id, Loan.student_id == student_id)).scalars().all()
    )
