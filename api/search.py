import os

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.embedded_text import embed_query
from app.models import LegalCase, User

router = APIRouter(prefix="/search")

# ความคล้ายแบบ cosine similarity (0–1); รับเฉพาะที่ "มากกว่า" 60% (ไม่รวมพอดี 60.00%)
MIN_COSINE_SIMILARITY = 0.6
VECTOR_CANDIDATE_LIMIT = 100
VECTOR_RESULT_LIMIT = 10


def _cosine_similarity(a: list, b: list) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


@router.post("/")
async def search_cases(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qv = embed_query(q)

    dist = LegalCase.embedding.cosine_distance(qv)
    candidates = (
        db.query(LegalCase)
        .filter(LegalCase.embedding.isnot(None))
        .order_by(dist)
        .limit(VECTOR_CANDIDATE_LIMIT)
        .all()
    )

    role = getattr(current_user, "role", "user") or "user"
    scored = []
    for r in candidates:
        if r.embedding is None:
            continue
        sim = _cosine_similarity(qv, list(r.embedding))
        if sim > MIN_COSINE_SIMILARITY:
            scored.append((sim, r))

    scored.sort(key=lambda x: -x[0])
    scored = scored[:VECTOR_RESULT_LIMIT]

    if not scored:
        return {
            "results": [],
            "count": 0,
            "message": "ไม่พบเอกสารที่มีความคล้ายกับคำค้นหามากกว่า 60% (cosine similarity)",
            "min_similarity": MIN_COSINE_SIMILARITY,
        }

    results = []
    for sim, r in scored:
        can_unblind = role == "admin" and r.created_by_user_id == current_user.id
        results.append(
            {
                "id": r.id,
                "casetype": r.casetype,
                "similarity": round(sim, 4),
                "similarity_percent": round(sim * 100, 2),
                "doc_path": r.doc_path if can_unblind else r.redacted_doc_path,
                "redacted_doc_path": r.redacted_doc_path,
                "can_view_unblinded": can_unblind,
            }
        )

    return {
        "results": results,
        "count": len(results),
        "min_similarity": MIN_COSINE_SIMILARITY,
    }

# GET เอกสารทั้งหมด
@router.get("/all")
async def get_all_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(LegalCase).all()

    return [
        {
            "id": r.id,
            "casetype": r.casetype,
            "doc_path": r.doc_path
            if getattr(current_user, "role", "user") == "admin" and r.created_by_user_id == current_user.id
            else r.redacted_doc_path,
            "redacted_doc_path": r.redacted_doc_path,
            "can_view_unblinded": getattr(current_user, "role", "user") == "admin"
            and r.created_by_user_id == current_user.id,
        }
        for r in rows
    ]

@router.get("/download/{case_id}")
async def download_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(LegalCase).filter(LegalCase.id == case_id).first()

    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")

    can_view_unblinded = getattr(current_user, "role", "user") == "admin" and row.created_by_user_id == current_user.id
    file_path = row.doc_path if can_view_unblinded else row.redacted_doc_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์เอกสาร")

    filename = os.path.basename(file_path)

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )