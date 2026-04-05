import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.document_access import (
    can_download_blind,
    can_download_unblind,
    can_list_document,
    can_mutate_document,
    can_publish_document,
    can_view_unblinded,
    doc_path_for_api,
)
from app.models import LegalCase, User
from app.case_pipeline import process_case_dict
from app.schemas import CaseRequest, DocumentPublishRequest

router = APIRouter(prefix="/documents", tags=["documents"])


def _case_request_payload(data: CaseRequest) -> dict:
    """รองรับทั้ง Pydantic v1 (.dict) และ v2 (.model_dump)."""
    dump = getattr(data, "model_dump", None)
    if callable(dump):
        return dump()
    return data.dict()


def _row_to_item(current_user: User, row: LegalCase) -> dict:
    return {
        "id": row.id,
        "casetype": row.casetype,
        "event_date": row.event_date,
        "created_at": row.created_at,
        "blind_published": bool(row.blind_published),
        "created_by_user_id": row.created_by_user_id,
        "doc_path": doc_path_for_api(current_user, row),
        "redacted_doc_path": row.redacted_doc_path,
        "can_view_unblinded": can_view_unblinded(current_user, row),
        "embedding_source_text": row.embedding_source_text
        if can_view_unblinded(current_user, row)
        else None,
    }


@router.post("")
async def create_document(
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    สร้างเอกสารจากฟอร์ม (โครงสร้างเดียวกับ POST /upload/json)
    ผู้ใช้ที่ล็อกอินแล้วสร้างได้ — ไม่จำกัดเฉพาะ admin
    """
    return process_case_dict(
        _case_request_payload(data),
        db,
        created_by_user_id=current_user.id,
    )


@router.get("")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(LegalCase).order_by(LegalCase.id.desc()).all()
    return [_row_to_item(current_user, r) for r in rows if can_list_document(current_user, r)]


@router.patch("/{case_id}/publish")
async def set_document_publish(
    case_id: int,
    body: DocumentPublishRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    if not can_publish_document(current_admin, row):
        raise HTTPException(status_code=403, detail="เฉพาะผู้สร้างเอกสาร (admin) เท่านั้นที่เผยแพร่/ถอนเผยแพร่ได้")
    row.blind_published = body.blind_published
    db.commit()
    db.refresh(row)
    return {"message": "อัปเดตสถานะเผยแพร่แล้ว", "blind_published": row.blind_published}


@router.get("/{case_id}/download")
async def download_document(
    case_id: int,
    version: str = Query("auto", description="auto | blind | unblinded"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row or not can_list_document(current_user, row):
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")

    if version == "unblinded":
        if not can_download_unblind(current_user, row):
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดาวน์โหลดฉบับเต็ม")
        file_path = row.doc_path
    elif version == "blind":
        if not can_download_blind(current_user, row):
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดาวน์โหลดฉบับ blind")
        file_path = row.redacted_doc_path
    else:
        file_path = doc_path_for_api(current_user, row)

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์เอกสาร")

    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/{case_id}")
async def get_document(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row or not can_list_document(current_user, row):
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return _row_to_item(current_user, row)


@router.put("/{case_id}")
async def regenerate_document(
    case_id: int,
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    if not can_mutate_document(current_user, row):
        raise HTTPException(status_code=403, detail="เฉพาะผู้สร้างเอกสารเท่านั้นที่แก้ไขได้")

    return process_case_dict(
        _case_request_payload(data),
        db,
        created_by_user_id=current_user.id,
        existing_row=row,
    )


@router.delete("/{case_id}")
async def delete_document(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    if not can_mutate_document(current_user, row):
        raise HTTPException(status_code=403, detail="เฉพาะผู้สร้างเอกสารเท่านั้นที่ลบได้")

    for p in [row.doc_path, row.redacted_doc_path, row.redacted_pdf_path]:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass

    db.delete(row)
    db.commit()
    return {"message": "Document deleted"}
