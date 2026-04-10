from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from app.auth import (
    generate_session_id,
    get_session_expiry,
    hash_password,
    session_cookie_flags,
    verify_password,
)
from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import Session, User
from app.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    LoginRequest,
    UserResponse,
)
router = APIRouter(prefix="/user_management", tags=["user_management"])
@router.post("/login")
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db),
):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    session_id = generate_session_id()
    expires_at = get_session_expiry(days=7)
    db.add(
        Session(
            session_id=session_id,
            user_id=user.id,
            expires_at=expires_at,
        )
    )
    db.commit()
    ck = session_cookie_flags(request)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        **ck,
    )
    return {"message": "Login success"}
@router.post("/logout")
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        db_session = (
            db.query(Session).filter(Session.session_id == session_id).first()
        )
        if db_session:
            db.delete(db_session)
            db.commit()
    ck = session_cookie_flags(request)
    response.delete_cookie(
        "session_id",
        path="/",
        httponly=True,
        secure=ck["secure"],
        samesite=ck["samesite"],
    )
    return {"message": "Logout success"}
@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role or "user",
    }
@router.get("/users")
async def list_users(
    db: DBSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "role": r.role or "user",
            "is_active": r.is_active,
            "created_at": r.created_at,
        }
        for r in rows
    ]
@router.post("/admin/users")
async def admin_create_user(
    data: AdminCreateUserRequest,
    db: DBSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing_user = db.query(User).filter(User.username == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "message": "User created",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role or "user",
            "is_active": user.is_active,
        },
    }
@router.patch("/admin/users/{user_id}")
async def admin_update_user(
    user_id: int,
    data: AdminUpdateUserRequest,
    db: DBSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.role is not None:
        if user.role == "admin" and data.role != "admin":
            other_admins = (
                db.query(func.count(User.id))
                .filter(User.role == "admin", User.id != user.id)
                .scalar()
                or 0
            )
            if other_admins < 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote the last admin",
                )
        user.role = data.role
    if data.is_active is not None:
        if not data.is_active and user.role == "admin":
            other_active_admins = (
                db.query(func.count(User.id))
                .filter(
                    User.role == "admin",
                    User.is_active.is_(True),
                    User.id != user.id,
                )
                .scalar()
                or 0
            )
            if other_active_admins < 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot deactivate the last active admin",
                )
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return {
        "message": "User updated",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role or "user",
            "is_active": user.is_active,
        },
    }
@router.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    db: DBSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        other_admins = (
            db.query(func.count(User.id))
            .filter(User.role == "admin", User.id != user.id)
            .scalar()
            or 0
        )
        if other_admins < 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last admin",
            )
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}
