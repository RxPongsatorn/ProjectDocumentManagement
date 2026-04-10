import os
from fastapi import FastAPI
from api.search import router as search_router
from api.user_management import router as user_management_router
from api.documents import router as documents_router
from api.dashboard import router as dashboard_router
from fastapi.middleware.cors import CORSMiddleware
from app.db import engine, ensure_schema
from app.models import LegalCase, User
from app.db import Base, SessionLocal
from app.auth import hash_password
app = FastAPI(title="Legal Document API")
Base.metadata.create_all(bind=engine)
ensure_schema()
def ensure_bootstrap_admin() -> None:
    db = SessionLocal()
    try:
        has_admin = db.query(User).filter(User.role == "admin").first() is not None
        if has_admin:
            return
        existing_admin_user = db.query(User).filter(User.username == "admin").first()
        if existing_admin_user:
            existing_admin_user.role = "admin"
            existing_admin_user.is_active = True
            if not existing_admin_user.password_hash:
                existing_admin_user.password_hash = hash_password("admin01")
            db.commit()
            return
        user = User(
            username="admin",
            password_hash=hash_password("admin01"),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
ensure_bootstrap_admin()
app.include_router(search_router)
app.include_router(user_management_router)
app.include_router(documents_router)
app.include_router(dashboard_router)
_default_origins = (
    "http://localhost:3000,http://localhost:5173,"
    "http://127.0.0.1:3000,http://127.0.0.1:5173"
)
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if o.strip()
]
_cors_origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https://[\w-]+\.ngrok-free\.app"
    r"|https://[\w-]+\.ngrok-free\.dev"
    r"|https://[\w-]+\.ngrok\.io"
    r"|https://[\w-]+\.ngrok\.app"
    r"|http://localhost(:\d+)?"
    r"|http://127\.0\.0\.1(:\d+)?"
    r"|https://localhost(:\d+)?"
    r"|https://127\.0\.0\.1(:\d+)?"
    r"|http://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?"
    r"|http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)