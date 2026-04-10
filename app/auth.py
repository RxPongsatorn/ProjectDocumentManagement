from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Any, Optional
from passlib.context import CryptContext
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)
def hash_password(password: str) -> str:
    return pwd_context.hash(password)
def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)
def generate_session_id() -> str:
    return secrets.token_urlsafe(32)
def get_session_expiry(days: int = 7) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)
def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")
def _effective_request_scheme(request: Any) -> str:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if forwarded in ("http", "https"):
        return forwarded
    return (getattr(request.url, "scheme", None) or "http").lower()
def _session_cookie_flags_from_env() -> dict:
    raw = (os.getenv("SESSION_COOKIE_SAMESITE") or "lax").strip().lower()
    samesite = raw if raw in ("lax", "strict", "none") else "lax"
    secure = _env_bool("SESSION_COOKIE_SECURE", False)
    if samesite == "none":
        secure = True
    return {"secure": secure, "samesite": samesite}
def session_cookie_flags(request: Optional[Any] = None) -> dict:
    if (
        os.getenv("SESSION_COOKIE_SAMESITE") is not None
        or os.getenv("SESSION_COOKIE_SECURE") is not None
    ):
        return _session_cookie_flags_from_env()
    if request is not None and _effective_request_scheme(request) == "https":
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}