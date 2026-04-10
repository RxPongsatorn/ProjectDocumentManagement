from __future__ import annotations
from typing import Any, Dict, Optional
from app.models import LegalCase, User
def is_admin(user: User) -> bool:
    return (getattr(user, "role", None) or "user") == "admin"
def can_view_unblinded(user: User, row: LegalCase) -> bool:
    return is_admin(user) and row.created_by_user_id == user.id
def has_public_blinded_copy(row: LegalCase) -> bool:
    return bool(row.redacted_doc_path and str(row.redacted_doc_path).strip())
def user_may_access_document(user: User, row: LegalCase) -> bool:
    if can_view_unblinded(user, row):
        return True
    if is_admin(user):
        return has_public_blinded_copy(row)
    return has_public_blinded_copy(row)
def resolve_doc_path_for_user(user: User, row: LegalCase) -> Optional[str]:
    if can_view_unblinded(user, row):
        return row.doc_path
    return row.redacted_doc_path
def serialize_case(
    user: User,
    row: LegalCase,
    *,
    include_embedding_text: bool = True,
) -> Dict[str, Any]:
    unblinded = can_view_unblinded(user, row)
    path = resolve_doc_path_for_user(user, row)
    return {
        "id": row.id,
        "casetype": row.casetype,
        "event_date": row.event_date,
        "created_at": row.created_at,
        "created_by_user_id": row.created_by_user_id,
        "doc_path": path,
        "redacted_doc_path": row.redacted_doc_path,
        "can_view_unblinded": unblinded,
        "variant_shown": "unblinded" if unblinded else "blinded",
        "has_blinded_file": has_public_blinded_copy(row),
        "embedding_source_text": (
            row.embedding_source_text if unblinded and include_embedding_text else None
        ),
    }
