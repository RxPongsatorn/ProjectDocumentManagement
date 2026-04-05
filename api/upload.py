# from fastapi import APIRouter, Depends
# from pydantic import BaseModel
# from sqlalchemy.orm import Session
# from app.ai_service import classify_text

# from app.generate_doc import generate_doc
# from app.generate_pdf import convert_docx_to_pdf
# from app.embedded_text import build_search_text, embed_text
# from app.db import get_db
# from app.models import LegalCase
# from app.build_redacted_data import build_redacted_data
# from app.case_pipeline import process_case_text, build_raw_text_from_json
# import json




import os
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.case_pipeline import process_case_text, process_case_dict
from app.pdf_service import extract_text_from_pdf, normalize_thai_text
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/upload")

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class CaseRequest(BaseModel):
    victim_name: str
    suspect_name: str
    event_date: str
    fact_summary: str
    legal_basis: str
    prosecutor_opinion: str
    filename: str | None = None
    casetype: str | None = None
    bank_account: str | None = None
    id_card: str | None = None
    plate_number: str | None = None


def _case_payload(data: CaseRequest) -> dict:
    dump = getattr(data, "model_dump", None)
    if callable(dump):
        return dump()
    return data.dict()


@router.post("/json")
async def upload_case_json(
    data: CaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    รับ JSON จากฟอร์ม — สร้าง Word จากข้อมูลตรงๆ (เส้นทางเดียวกับ POST /documents)
    ไม่ผ่าน LLM re-extract เพื่อไม่ให้ค่าจากฟอร์มเพี้ยน
    """
    return process_case_dict(
        _case_payload(data),
        db,
        created_by_user_id=current_user.id,
    )

@router.post("/pdf")
async def upload_case_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")

    save_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = extract_text_from_pdf(save_path)
    normalized_text = normalize_thai_text(extracted_text)

    if not normalized_text:
        raise HTTPException(status_code=400, detail="ไม่สามารถอ่านข้อความจาก PDF ได้")

    return process_case_text(normalized_text, db, created_by_user_id=current_user.id)