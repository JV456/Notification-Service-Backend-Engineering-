from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PreferenceIn, PreferenceOut
from app.services.notification_service import get_user_preference

router = APIRouter(tags=["preferences"])


@router.post("/users/{user_id}/preferences", response_model=PreferenceOut)
def set_preferences(user_id: str, payload: PreferenceIn, db: Session = Depends(get_db)):
    """Set channel opt-in/opt-out for a user. Only fields included in the body are changed."""
    pref = get_user_preference(db, user_id)
    if payload.email_enabled is not None:
        pref.email_enabled = payload.email_enabled
    if payload.sms_enabled is not None:
        pref.sms_enabled = payload.sms_enabled
    if payload.push_enabled is not None:
        pref.push_enabled = payload.push_enabled
    db.commit()
    db.refresh(pref)
    return pref


@router.get("/users/{user_id}/preferences", response_model=PreferenceOut)
def get_preferences(user_id: str, db: Session = Depends(get_db)):
    """Get a user's channel preferences (defaults to all channels enabled if never set)."""
    return get_user_preference(db, user_id)
