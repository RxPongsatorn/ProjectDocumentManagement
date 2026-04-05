import os
from typing import Literal

CookieSameSite = Literal["lax", "strict", "none"]


def session_cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")


def session_cookie_samesite() -> CookieSameSite:
    raw = (os.getenv("SESSION_COOKIE_SAMESITE", "lax") or "lax").lower()
    if raw not in ("lax", "strict", "none"):
        return "lax"
    return raw  # type: ignore[return-value]


def session_cookie_settings() -> tuple[bool, CookieSameSite]:
    """
    ค่า cookie สำหรับ session_id ตอน login/logout

    Cross-site (frontend คนละโดเมนกับ API): ตั้ง
      SESSION_COOKIE_SAMESITE=none
      SESSION_COOKIE_SECURE=true
    และต้องใช้ HTTPS (เบราว์เซอร์กำหนดว่า SameSite=None ต้องคู่กับ Secure)

    Dev แบบ HTTP localhost: ใช้ค่าเริ่ม lax + secure=false หรือตั้งเองใน .env
    """
    secure = session_cookie_secure()
    samesite = session_cookie_samesite()
    if samesite == "none" and not secure:
        secure = True
    return secure, samesite
