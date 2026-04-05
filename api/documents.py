import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import LegalCase, User
from app.case_pipeline import build_raw_text_from_json, process_case_text
from app.schemas import CaseRequest

router = APIRouter(prefix="/documents", tags=["documents"])


def _can_view_unblinded(current_user: User, row: LegalCase) -> bool:
    return getattr(current_user, "role", "user") == "admin" and row.created_by_user_id == current_user.id


@router.post("")
async def create_document(
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    raw_text = build_raw_text_from_json(data.dict())
    return process_case_text(raw_text, db, created_by_user_id=current_admin.id)


@router.get("")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(LegalCase).order_by(LegalCase.id.desc()).all()

    results = []
    for r in rows:
        can_unblinded = _can_view_unblinded(current_user, r)
        results.append(
            {
                "id": r.id,
                "casetype": r.casetype,
                "event_date": r.event_date,
                "created_at": r.created_at,
                # Keep backwards compatibility with previous APIs:
                # `doc_path` is what the client is allowed to download.
                "doc_path": r.doc_path if can_unblinded else r.redacted_doc_path,
                "redacted_doc_path": r.redacted_doc_path,
                "can_view_unblinded": can_unblinded,
            }
        )
    return results


@router.get("/{case_id}")
async def get_document(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")

    can_unblinded = _can_view_unblinded(current_user, row)
    return {
        "id": row.id,
        "casetype": row.casetype,
        "event_date": row.event_date,
        "created_at": row.created_at,
        "doc_path": row.doc_path if can_unblinded else row.redacted_doc_path,
        "redacted_doc_path": row.redacted_doc_path,
        "can_view_unblinded": can_unblinded,
    }


@router.get("/{case_id}/download")
async def download_document(
    case_id: int,
    version: str = Query("auto", description="auto | blind | unblinded"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")

    can_unblinded = _can_view_unblinded(current_user, row)

    if version == "unblinded":
        if not can_unblinded:
            raise HTTPException(status_code=403, detail="Only the creator admin can access unblinded doc")
        file_path = row.doc_path
    elif version == "blind":
        file_path = row.redacted_doc_path
    else:
        file_path = row.doc_path if can_unblinded else row.redacted_doc_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์เอกสาร")

    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.put("/{case_id}")
async def regenerate_document(
    case_id: int,
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")

    if row.created_by_user_id != current_admin.id:
        raise HTTPException(status_code=403, detail="Only the creator admin can modify this document")

    raw_text = build_raw_text_from_json(data.dict())
    return process_case_text(raw_text, db, created_by_user_id=current_admin.id, existing_row=row)


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
        raise HTTPException(status_code=403, detail="Only the creator admin can delete this document")

    # Best-effort cleanup of files; ignore missing files.
    for p in [row.doc_path, row.redacted_doc_path, row.redacted_pdf_path]:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass

    db.delete(row)
    db.commit()
    return {"message": "Document deleted"}

