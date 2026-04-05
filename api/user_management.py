from fastapi import HTTPException, Response, Request, status
from sqlalchemy.orm import Session as DBSession
from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.db import get_db
from app.models import User, Session
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
)
from app.auth import hash_password, verify_password, generate_session_id, get_session_expiry
from app.config import session_cookie_settings
from app.deps import get_current_user, require_admin

router = APIRouter(prefix="/user_management", tags=["user_management"])

@router.post("/register")
def register(data: RegisterRequest, db: DBSession = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Register success",
        "user": {
            "id": user.id,
            "username": user.username
        }
    }


@router.post("/login")
def login(data: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    session_id = generate_session_id()
    expires_at = get_session_expiry(days=7)

    session = Session(
        session_id=session_id,
        user_id=user.id,
        expires_at=expires_at
    )
    db.add(session)
    db.commit()

    cookie_secure, cookie_samesite = session_cookie_settings()
    response.set_cookie(
        key="session_id",
        value=session_id,
        path="/",
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=60 * 60 * 24 * 7,
    )

    return {"message": "Login success"}


@router.post("/logout")
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    session_id = request.cookies.get("session_id")

    if session_id:
        db_session = db.query(Session).filter(Session.session_id == session_id).first()
        if db_session:
            db.delete(db_session)
            db.commit()

    cookie_secure, cookie_samesite = session_cookie_settings()
    response.delete_cookie(
        "session_id",
        path="/",
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
    )
    return {"message": "Logout success"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role or "user",
    }


def _serialize_users(db: DBSession):
    rows = db.query(User).order_by(User.id).all()
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


@router.get("/users")
async def list_users(
    db: DBSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return _serialize_users(db)


@router.get("/all")
async def list_users_legacy(
    db: DBSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return _serialize_users(db)


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
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = data.role if data.role is not None else (user.role or "user")
    new_active = data.is_active if data.is_active is not None else bool(user.is_active)

    was_effective_admin = (user.role or "user") == "admin" and user.is_active
    will_effective_admin = new_role == "admin" and new_active

    if was_effective_admin and not will_effective_admin:
        other_admins = (
            db.query(func.count(User.id))
            .filter(
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
            .scalar()
            or 0
        )
        if other_admins < 1:
            raise HTTPException(
                status_code=400,
                detail="ต้องมีบัญชี admin อย่างน้อย 1 บัญชี",
            )

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
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
        raise HTTPException(status_code=400, detail="ไม่สามารถลบบัญชีของตัวเองได้")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if (user.role or "user") == "admin" and user.is_active:
        other_admins = (
            db.query(func.count(User.id))
            .filter(
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
            .scalar()
            or 0
        )
        if other_admins < 1:
            raise HTTPException(
                status_code=400,
                detail="ไม่สามารถลบ admin คนสุดท้ายได้",
            )

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}