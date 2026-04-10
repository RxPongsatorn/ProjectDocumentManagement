import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.case_pipeline import process_case_dict
from app.db import get_db
from app.deps import get_current_user, require_admin
from app.document_access import (
    can_view_unblinded,
    is_admin,
    resolve_doc_path_for_user,
    serialize_case,
    user_may_access_document,
)
from app.models import LegalCase, User
from app.schemas import CaseRequest
router = APIRouter(prefix="/documents", tags=["documents"])
@router.post("")
async def create_document(
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return process_case_dict(data.dict(), db, created_by_user_id=current_admin.id)
@router.get("")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(LegalCase).order_by(LegalCase.id.desc())
    if not is_admin(current_user):
        q = q.filter(LegalCase.redacted_doc_path.isnot(None)).filter(
            LegalCase.redacted_doc_path != ""
        )
    rows = q.all()
    return [serialize_case(current_user, r) for r in rows]
@router.get("/{case_id}")
async def get_document(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row or not user_may_access_document(current_user, row):
        raise HTTPException(status_code=404, detail="ไม่พบเอกสารหรือไม่มีสิทธิ์เข้าถึง")
    return serialize_case(current_user, row)
@router.get("/{case_id}/download")
async def download_document(
    case_id: int,
    version: str = Query("auto", description="auto | blind | unblinded"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row or not user_may_access_document(current_user, row):
        raise HTTPException(status_code=404, detail="ไม่พบเอกสารหรือไม่มีสิทธิ์เข้าถึง")
    can_ub = can_view_unblinded(current_user, row)
    if version == "unblinded":
        if not can_ub:
            raise HTTPException(
                status_code=403,
                detail="เฉพาะ admin ที่เป็นผู้สร้างเอกสารจึงดาวน์โหลดเวอร์ชันเต็มได้",
            )
        file_path = row.doc_path
    elif version == "blind":
        file_path = row.redacted_doc_path
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์เอกสารแบบ blind")
    else:
        file_path = resolve_doc_path_for_user(current_user, row)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์เอกสาร")
    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
@router.put("/{case_id}")
async def update_document(
    case_id: int,
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    if row.created_by_user_id != current_admin.id:
        raise HTTPException(
            status_code=403, detail="แก้ไขได้เฉพาะเอกสารที่คุณเป็นผู้สร้าง"
        )
    return process_case_dict(
        data.dict(), db, created_by_user_id=current_admin.id, existing_row=row
    )
@router.delete("/{case_id}")
async def delete_document(
    case_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    if row.created_by_user_id != current_admin.id:
        raise HTTPException(
            status_code=403, detail="ลบได้เฉพาะเอกสารที่คุณเป็นผู้สร้าง"
        )
    for p in [row.doc_path, row.redacted_doc_path, row.redacted_pdf_path]:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    db.delete(row)
    db.commit()
    return {"message": "ลบเอกสารแล้ว"}
