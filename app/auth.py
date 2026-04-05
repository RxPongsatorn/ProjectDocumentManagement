from datetime import datetime, timedelta, timezone
import secrets
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