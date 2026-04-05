"""สถิติสำหรับ dashboard — เฉพาะ admin."""
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import require_admin
from app.models import LegalCase, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = (
        db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    )
    admin_users = (
        db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
    )
    regular_users = (
        db.query(func.count(User.id))
        .filter(or_(User.role == "user", User.role.is_(None)))
        .scalar()
        or 0
    )

    total_docs = db.query(func.count(LegalCase.id)).scalar() or 0
    published = (
        db.query(func.count(LegalCase.id))
        .filter(LegalCase.blind_published.is_(True))
        .scalar()
        or 0
    )
    draft = total_docs - published

    casetype_rows = (
        db.query(LegalCase.casetype, func.count(LegalCase.id))
        .group_by(LegalCase.casetype)
        .all()
    )
    by_casetype = [
        {
            "casetype": (ct or "").strip() or "(ไม่ระบุ)",
            "count": cnt,
        }
        for ct, cnt in casetype_rows
    ]
    by_casetype.sort(key=lambda x: -x["count"])

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "by_role": {"admin": admin_users, "user": regular_users},
        },
        "documents": {
            "total": total_docs,
            "blind_published": published,
            "draft_not_published": draft,
            "by_casetype": by_casetype,
        },
    }
