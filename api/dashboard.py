from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import require_admin
from app.document_access import legal_case_has_content_clause
from app.models import LegalCase, User
router = APIRouter(prefix="/admin", tags=["admin_dashboard"])
@router.get("/dashboard")
def admin_dashboard(
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
        .filter((User.role == "user") | (User.role.is_(None)))
        .scalar()
        or 0
    )
    total_documents = db.query(func.count(LegalCase.id)).scalar() or 0
    with_blinded = (
        db.query(func.count(LegalCase.id))
        .filter(legal_case_has_content_clause())
        .scalar()
        or 0
    )
    rows = (
        db.query(LegalCase.casetype, func.count(LegalCase.id))
        .group_by(LegalCase.casetype)
        .all()
    )
    merged: dict[str, int] = defaultdict(int)
    for ct, cnt in rows:
        key = (ct or "").strip() or "ไม่ระบุ"
        merged[key] += int(cnt)
    documents_by_casetype = sorted(
        [{"casetype": k, "count": v} for k, v in merged.items()],
        key=lambda x: -x["count"],
    )
    return {
        "users": {
            "total": int(total_users),
            "active": int(active_users),
            "admins": int(admin_users),
            "regular": int(regular_users),
        },
        "documents": {
            "total": int(total_documents),
            "with_blinded_file": int(with_blinded),
            "by_casetype": documents_by_casetype,
        },
    }