from __future__ import annotations
from typing import Any, Dict, Optional

from sqlalchemy import or_
from sqlalchemy.sql import func as sqlfunc

from app.build_redacted_data import build_redacted_data
from app.models import LegalCase, User


def row_has_case_content(row: LegalCase) -> bool:
    return any(
        [
            (row.victim_name or "").strip(),
            (row.suspect_name or "").strip(),
            (row.fact_summary or "").strip(),
            (row.legal_basis or "").strip(),
            (row.prosecutor_opinion or "").strip(),
        ]
    )


def legal_case_has_content_clause():
    """SQL expression: case has at least one non-empty core text field."""

    def _nonempty(col):
        return sqlfunc.nullif(sqlfunc.trim(sqlfunc.coalesce(col, "")), "").isnot(None)

    return or_(
        _nonempty(LegalCase.victim_name),
        _nonempty(LegalCase.suspect_name),
        _nonempty(LegalCase.fact_summary),
        _nonempty(LegalCase.legal_basis),
        _nonempty(LegalCase.prosecutor_opinion),
    )


def _case_fields_for_response(row: LegalCase) -> dict:
    return {
        "victim_name": row.victim_name or "",
        "suspect_name": row.suspect_name or "",
        "fact_summary": row.fact_summary or "",
        "legal_basis": row.legal_basis or "",
        "prosecutor_opinion": row.prosecutor_opinion or "",
        "bank_account": row.bank_account or "",
        "id_card": row.id_card or "",
        "plate_number": row.plate_number or "",
    }
def is_admin(user: User) -> bool:
    return (getattr(user, "role", None) or "user") == "admin"
def can_view_unblinded(user: User, row: LegalCase) -> bool:
    return is_admin(user) and row.created_by_user_id == user.id
def has_public_blinded_copy(row: LegalCase) -> bool:
    """True if blind/download variant can be produced (has case content in DB)."""
    return row_has_case_content(row)

def user_may_access_document(user: User, row: LegalCase) -> bool:
    if not row_has_case_content(row):
        return False
    if can_view_unblinded(user, row):
        return True
    if is_admin(user):
        return True
    return True
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
    raw = _case_fields_for_response(row)
    if unblinded:
        content = raw
    else:
        content = build_redacted_data(raw)
    return {
        "id": row.id,
        "casetype": row.casetype,
        "event_date": row.event_date,
        "created_at": row.created_at,
        "created_by_user_id": row.created_by_user_id,
        "victim_name": content["victim_name"],
        "suspect_name": content["suspect_name"],
        "fact_summary": content["fact_summary"],
        "legal_basis": content["legal_basis"],
        "prosecutor_opinion": content["prosecutor_opinion"],
        "doc_path": path,
        "redacted_doc_path": row.redacted_doc_path,
        "documents_generated": row_has_case_content(row),
        "can_view_unblinded": unblinded,
        "variant_shown": "unblinded" if unblinded else "blinded",
        "has_blinded_file": row_has_case_content(row),
        "embedding_source_text": (
            row.embedding_source_text if unblinded and include_embedding_text else None
        ),
    }
