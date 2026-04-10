from app.ai_service import classify_text
from app.embedded_text import build_search_text, embed_text
from app.generate_doc import generate_doc
from app.generate_pdf import convert_docx_to_pdf
from app.build_redacted_data import build_redacted_data
from app.models import LegalCase
def process_case_text(
    raw_text: str,
    db,
    created_by_user_id: int | None = None,
    existing_row: LegalCase | None = None,
):
    text_extraction = classify_text(raw_text)
    search_text = build_search_text(text_extraction)
    embedding = embed_text(search_text)
    original_doc = generate_doc(text_extraction)
    redacted_data = build_redacted_data(text_extraction)
    redacted_doc = generate_doc(redacted_data)
    redacted_pdf = convert_docx_to_pdf(redacted_doc)
    if existing_row is None:
        row = LegalCase(
            casetype=text_extraction.get("case_type") or "",
            event_date=text_extraction.get("event_date") or "",
            embedding=embedding,
            embedding_source_text=search_text,
            doc_path=original_doc,
            redacted_doc_path=redacted_doc,
            redacted_pdf_path=redacted_pdf,
            created_by_user_id=created_by_user_id,
        )
        db.add(row)
    else:
        row = existing_row
        row.casetype = text_extraction.get("case_type") or ""
        row.event_date = text_extraction.get("event_date") or ""
        row.embedding = embedding
        row.embedding_source_text = search_text
        row.doc_path = original_doc
        row.redacted_doc_path = redacted_doc
        row.redacted_pdf_path = redacted_pdf
    db.commit()
    db.refresh(row)
    return {
        "status": "done",
        "case_id": row.id,
        "file_path": original_doc,
        "redacted_file_path": redacted_doc,
        "redacted_pdf_path": redacted_pdf,
        "extraction": text_extraction,
        "embedding_source_text": search_text,
    }
def process_case_dict(
    case_data: dict,
    db,
    created_by_user_id: int | None = None,
    existing_row: LegalCase | None = None,
):
    redacted_data = build_redacted_data(case_data)
    search_text = build_search_text(redacted_data)
    embedding = embed_text(search_text)
    original_doc = generate_doc(case_data)
    redacted_doc = generate_doc(redacted_data)
    redacted_pdf = convert_docx_to_pdf(redacted_doc)
    if existing_row is None:
        row = LegalCase(
            casetype=case_data.get("casetype") or case_data.get("case_type") or "",
            event_date=case_data.get("event_date") or "",
            embedding=embedding,
            embedding_source_text=search_text,
            doc_path=original_doc,
            redacted_doc_path=redacted_doc,
            redacted_pdf_path=redacted_pdf,
            created_by_user_id=created_by_user_id,
        )
        db.add(row)
    else:
        row = existing_row
        row.casetype = case_data.get("casetype") or case_data.get("case_type") or ""
        row.event_date = case_data.get("event_date") or ""
        row.embedding = embedding
        row.embedding_source_text = search_text
        row.doc_path = original_doc
        row.redacted_doc_path = redacted_doc
        row.redacted_pdf_path = redacted_pdf
    db.commit()
    db.refresh(row)
    return {
        "status": "done",
        "case_id": row.id,
        "file_path": original_doc,
        "redacted_file_path": redacted_doc,
        "redacted_pdf_path": redacted_pdf,
        "extraction": case_data,
        "embedding_source_text": search_text,
    }
def build_raw_text_from_json(case_data: dict) -> str:
    return f"""
ผู้เสียหาย: {case_data.get('victim_name', '')}
ผู้ต้องหา: {case_data.get('suspect_name', '')}
วันเกิดเหตุ: {case_data.get('event_date', '')}
ข้อเท็จจริง: {case_data.get('fact_summary', '')}
ข้อกฎหมาย: {case_data.get('legal_basis', '')}
ความเห็นอัยการ: {case_data.get('prosecutor_opinion', '')}
ประเภทคดี: {case_data.get('casetype', '')}
บัญชีธนาคาร: {case_data.get('bank_account', '')}
บัตรประชาชน: {case_data.get('id_card', '')}
เลขทะเบียนรถ: {case_data.get('plate_number', '')}
""".strip()