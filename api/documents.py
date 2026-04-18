import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.build_redacted_data import build_redacted_data
from app.case_pipeline import _case_dict_from_row, finalize_case_documents, process_case_dict
from app.db import get_db
from app.deps import get_current_user, require_admin
from app.document_access import (
    can_view_unblinded,
    is_admin,
    legal_case_has_content_clause,
    row_has_case_content,
    serialize_case,
    user_may_access_document,
)
from app.generate_doc import render_docx_to_file
from app.models import LegalCase, User
from app.schemas import BulkCaseImportRequest, CaseRequest

router = APIRouter(prefix="/documents", tags=["documents"])


def _unlink_silent(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


@router.post("")
async def create_document(
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return process_case_dict(data.dict(), db, created_by_user_id=current_admin.id)


_MAX_BULK = 500


@router.post("/bulk")
def import_documents_bulk(
    body: BulkCaseImportRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Import many cases in one request (same rules as POST /documents per row)."""
    if len(body.items) > _MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail=f"Too many items (max {_MAX_BULK} per request)",
        )
    results: list[dict] = []
    errors: list[dict] = []
    for idx, item in enumerate(body.items):
        try:
            saved = process_case_dict(
                item.dict(), db, created_by_user_id=current_admin.id
            )
            results.append(
                {
                    "index": idx,
                    "case_id": saved["case_id"],
                    "status": saved.get("status", "saved"),
                }
            )
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})
    return {
        "saved_count": len(results),
        "failed_count": len(errors),
        "results": results,
        "errors": errors,
    }


@router.get("")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(LegalCase)
        .filter(legal_case_has_content_clause())
        .order_by(LegalCase.id.desc())
    )
    rows = q.all()
    return [serialize_case(current_user, r) for r in rows]


@router.post("/cases/{case_id}/generate-files")
def api_generate_case_files(
    case_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    if row.created_by_user_id != current_admin.id:
        raise HTTPException(
            status_code=403,
            detail='สร้างไฟล์ได้เฉพาะคดีที่คุณเป็นผู้สร้าง',
        )
    result = finalize_case_documents(case_id, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/by-user/{user_id}/count")
def count_documents_by_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Count legal_cases rows where created_by_user_id matches (creator)."""
    if not is_admin(current_user) and user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only admins may view another user's document count.",
        )
    if db.query(User.id).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")
    n = (
        db.query(func.count(LegalCase.id))
        .filter(LegalCase.created_by_user_id == user_id)
        .scalar()
    )
    return {"user_id": user_id, "document_count": int(n or 0)}


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
    if not row_has_case_content(row):
        raise HTTPException(
            status_code=404,
            detail="ไม่มีข้อมูลคดีเพียงพอสำหรับสร้างเอกสาร",
        )
    can_ub = can_view_unblinded(current_user, row)
    base = _case_dict_from_row(row)
    if version == "unblinded":
        if not can_ub:
            raise HTTPException(
                status_code=403,
                detail='เฉพาะ admin ที่เป็นผู้สร้างเอกสารจึงดาวน์โหลดเวอร์ชันเต็มได้',
            )
        case_data = base
        suffix = "unblinded"
    elif version == "blind":
        case_data = build_redacted_data(base)
        suffix = "blind"
    else:
        if can_ub:
            case_data = base
            suffix = "unblinded"
        else:
            case_data = build_redacted_data(base)
            suffix = "blind"
    fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    try:
        render_docx_to_file(case_data, tmp_path)
    except Exception:
        _unlink_silent(tmp_path)
        raise HTTPException(status_code=500, detail="สร้างเอกสารไม่สำเร็จ")
    filename = f"case_{case_id}_{suffix}.docx"
    return FileResponse(
        path=tmp_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        background=BackgroundTask(lambda p=tmp_path: _unlink_silent(p)),
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
            status_code=403, detail='แก้ไขได้เฉพาะเอกสารที่คุณนันเป็นผู้สร้าง'
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
            status_code=403, detail='ลบได้เฉพาะเอกสารที่คุณนันเป็นผู้สร้าง'
        )
    for p in [row.doc_path, row.redacted_doc_path]:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    db.delete(row)
    db.commit()
    return {"message": "ลบเอกสารแล้ว"}
