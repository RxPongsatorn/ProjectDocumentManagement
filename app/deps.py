from datetime import datetime, timezone
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from app.db import get_db
from app.models import Session, User
def get_current_user(
    request: Request,
    db: DBSession = Depends(get_db)
) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    db_session = (
        db.query(Session)
        .filter(Session.session_id == session_id)
        .first()
    )
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    if db_session.expires_at < datetime.now(timezone.utc):
        db.delete(db_session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )
    user = db_session.user
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )
    return current_user