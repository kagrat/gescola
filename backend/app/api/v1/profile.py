from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.profile import MySignatureOut, MySignatureUpdate
from app.services.profile_service import get_my_signature, update_my_signature

router = APIRouter(tags=["profile"])


@router.get("/users/me/signature", response_model=MySignatureOut)
def get_my_signature_endpoint(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user),
) -> MySignatureOut:
    return get_my_signature(db, current_user.id)


@router.patch("/users/me/signature", response_model=MySignatureOut)
def update_my_signature_endpoint(
    payload: MySignatureUpdate, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user),
) -> MySignatureOut:
    return update_my_signature(db, user_id=current_user.id, data=payload)
