import os
from typing import Any

from app.ai_service import classify_text
from app.build_redacted_data import build_redacted_data
from app.embedded_text import build_search_text, embed_text
from app.generate_doc import generate_doc
from app.models import LegalCase


def _normalize_case_payload(case_data: dict) -> dict:
    out = dict(case_data)
    ct = out.get("casetype") or out.get("case_type")
    if ct is not None:
        out["casetype"] = ct or ""
    return out


def _case_dict_from_row(row: LegalCase) -> dict:
    return {
        "victim_name": row.victim_name or "",
        "suspect_name": row.suspect_name or "",
        "event_date": row.event_date or "",
        "fact_summary": row.fact_summary or "",
        "legal_basis": row.legal_basis or "",
        "prosecutor_opinion": row.prosecutor_opinion or "",
        "filename": row.filename,
        "casetype": row.casetype or "",
        "case_type": row.casetype or "",
        "bank_account": row.bank_account or "",
        "id_card": row.id_card or "",
        "plate_number": row.plate_number or "",
    }


def _apply_payload_to_row(row: LegalCase, payload: dict) -> None:
    row.filename = payload.get("filename")
    row.casetype = payload.get("casetype") or payload.get("case_type") or ""
    row.event_date = payload.get("event_date") or ""
    row.victim_name = payload.get("victim_name") or ""
    row.suspect_name = payload.get("suspect_name") or ""
    row.fact_summary = payload.get("fact_summary") or ""
    row.legal_basis = payload.get("legal_basis") or ""
    row.prosecutor_opinion = payload.get("prosecutor_opinion") or ""
    row.bank_account = payload.get("bank_account") or ""
    row.id_card = payload.get("id_card") or ""
    row.plate_number = payload.get("plate_number") or ""


def _row_has_case_content(row: LegalCase) -> bool:
    return any(
        [
            (row.victim_name or "").strip(),
            (row.suspect_name or "").strip(),
            (row.fact_summary or "").strip(),
            (row.legal_basis or "").strip(),
            (row.prosecutor_opinion or "").strip(),
        ]
    )


def _strip_file_paths(row: LegalCase) -> None:
    row.doc_path = None
    row.redacted_doc_path = None


def _remove_disk_files(row: LegalCase) -> None:
    for p in (row.doc_path, row.redacted_doc_path):
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def _persist_case_row(
    case_data: dict,
    db,
    created_by_user_id: int | None = None,
    existing_row: LegalCase | None = None,
) -> LegalCase:
    payload = _normalize_case_payload(case_data)
    redacted_data = build_redacted_data(payload)
    search_text = build_search_text(redacted_data)
    embedding = embed_text(search_text)

    if existing_row is None:
        row = LegalCase(
            embedding=embedding,
            embedding_source_text=search_text,
            doc_path=None,
            redacted_doc_path=None,
            created_by_user_id=created_by_user_id,
        )
        _apply_payload_to_row(row, payload)
        row.fact_summary_blinded = redacted_data.get("fact_summary") or ""
        db.add(row)
    else:
        row = existing_row
        _remove_disk_files(row)
        _strip_file_paths(row)
        _apply_payload_to_row(row, payload)
        row.embedding = embedding
        row.embedding_source_text = search_text
        row.fact_summary_blinded = redacted_data.get("fact_summary") or ""
    db.commit()
    db.refresh(row)
    return row


def _write_generated_files(row: LegalCase, db) -> dict[str, Any]:
    if not _row_has_case_content(row):
        raise ValueError(
            "\u0e44\u0e21\u0e48\u0e21\u0e35\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e04\u0e14\u0e35\u0e43\u0e19\u0e41\u0e16\u0e27\u0e17\u0e35\u0e48\u0e40\u0e01\u0e47\u0e1a\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01"
        )
    case_data = _case_dict_from_row(row)
    _remove_disk_files(row)
    _strip_file_paths(row)
    redacted_data = build_redacted_data(case_data)
    original_doc = generate_doc(case_data)
    redacted_doc = generate_doc(redacted_data)
    row.doc_path = original_doc
    row.redacted_doc_path = redacted_doc
    db.commit()
    db.refresh(row)
    return {
        "status": "done",
        "case_id": row.id,
        "file_path": original_doc,
        "redacted_file_path": redacted_doc,
    }


def finalize_case_documents(case_id: int, db) -> dict[str, Any]:
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        return {"error": "\u0e44\u0e21\u0e48\u0e1e\u0e1a\u0e40\u0e2d\u0e01\u0e2a\u0e32\u0e23"}
    if not _row_has_case_content(row):
        return {
            "error": (
                "\u0e44\u0e21\u0e48\u0e21\u0e35\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e04\u0e14\u0e35\u0e43\u0e19\u0e41\u0e16\u0e27 "
                "\u0e43\u0e2b\u0e49\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e01\u0e48\u0e2d\u0e19"
            )
        }
    try:
        return _write_generated_files(row, db)
    except ValueError as e:
        return {"error": str(e)}


def process_case_text(
    raw_text: str,
    db,
    created_by_user_id: int | None = None,
    existing_row: LegalCase | None = None,
):
    text_extraction = classify_text(raw_text)
    case_payload = _normalize_case_payload(text_extraction)
    row = _persist_case_row(
        case_payload, db, created_by_user_id=created_by_user_id, existing_row=existing_row
    )
    redacted_data = build_redacted_data(case_payload)
    search_text = build_search_text(redacted_data)
    return {
        "status": "saved",
        "case_id": row.id,
        "documents_generated": False,
        "file_path": row.doc_path,
        "redacted_file_path": row.redacted_doc_path,
        "extraction": text_extraction,
        "embedding_source_text": search_text,
    }


def process_case_dict(
    case_data: dict,
    db,
    created_by_user_id: int | None = None,
    existing_row: LegalCase | None = None,
):
    payload = _normalize_case_payload(case_data)
    row = _persist_case_row(
        payload, db, created_by_user_id=created_by_user_id, existing_row=existing_row
    )
    redacted_data = build_redacted_data(payload)
    search_text = build_search_text(redacted_data)
    return {
        "status": "saved",
        "case_id": row.id,
        "documents_generated": _row_has_case_content(row),
        "file_path": row.doc_path,
        "redacted_file_path": row.redacted_doc_path,
        "extraction": payload,
        "embedding_source_text": search_text,
    }


def build_raw_text_from_json(case_data: dict) -> str:
    return build_raw_text_from_row_fields(_normalize_case_payload(case_data))


def build_raw_text_from_row(row: LegalCase) -> str:
    return build_raw_text_from_row_fields(_case_dict_from_row(row))


def build_raw_text_from_row_fields(d: dict) -> str:
    v = d.get("victim_name", "")
    s = d.get("suspect_name", "")
    ed = d.get("event_date", "")
    fs = d.get("fact_summary", "")
    lb = d.get("legal_basis", "")
    po = d.get("prosecutor_opinion", "")
    ct = d.get("casetype", "")
    ba = d.get("bank_account", "")
    ic = d.get("id_card", "")
    pn = d.get("plate_number", "")
    return (
        f"\u0e1c\u0e39\u0e49\u0e40\u0e2a\u0e35\u0e22\u0e2b\u0e32\u0e22: {v}\n"
        f"\u0e1c\u0e39\u0e49\u0e15\u0e49\u0e2d\u0e07\u0e2b\u0e32: {s}\n"
        f"\u0e27\u0e31\u0e19\u0e40\u0e01\u0e34\u0e14\u0e40\u0e2b\u0e15\u0e38: {ed}\n"
        f"\u0e02\u0e49\u0e2d\u0e40\u0e17\u0e47\u0e08\u0e08\u0e23\u0e34\u0e07: {fs}\n"
        f"\u0e02\u0e49\u0e2d\u0e01\u0e0e\u0e2b\u0e21\u0e32\u0e22: {lb}\n"
        f"\u0e04\u0e27\u0e32\u0e21\u0e40\u0e2b\u0e47\u0e19\u0e2d\u0e31\u0e22\u0e01\u0e32\u0e23: {po}\n"
        f"\u0e1b\u0e23\u0e30\u0e40\u0e20\u0e17\u0e04\u0e14\u0e35: {ct}\n"
        f"\u0e1a\u0e31\u0e0d\u0e0a\u0e35\u0e18\u0e19\u0e32\u0e04\u0e32\u0e23: {ba}\n"
        f"\u0e1a\u0e31\u0e15\u0e23\u0e1b\u0e23\u0e30\u0e0a\u0e32\u0e0a\u0e19: {ic}\n"
        f"\u0e40\u0e25\u0e02\u0e17\u0e30\u0e40\u0e1a\u0e35\u0e22\u0e19\u0e23\u0e16: {pn}"
    )
