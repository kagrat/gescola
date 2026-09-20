import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import Attendance
from app.schemas.grade import AttendanceCreate
from app.services.academic_service import get_student_or_404


def create_attendance(db: Session, *, tenant_id: uuid.UUID, data: AttendanceCreate) -> Attendance:
    get_student_or_404(db, tenant_id=tenant_id, student_id=data.student_id)
    obj = Attendance(
        tenant_id=tenant_id,
        student_id=data.student_id,
        date=data.date,
        status=data.status,
        justified=data.justified,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_attendance(db: Session, *, tenant_id: uuid.UUID, student_id: uuid.UUID) -> list[Attendance]:
    get_student_or_404(db, tenant_id=tenant_id, student_id=student_id)
    return list(
        db.execute(
            select(Attendance).where(Attendance.tenant_id == tenant_id, Attendance.student_id == student_id)
        ).scalars().all()
    )
