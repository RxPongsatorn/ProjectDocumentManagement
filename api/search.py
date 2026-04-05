import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.document_access import can_list_document, can_view_unblinded, doc_path_for_api
from app.embedded_text import embed_query
from app.models import LegalCase, User

router = APIRouter(prefix="/search")

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


def _visible_cases_filter(current_user: User):
    """เผยแพร่แล้ว หรือฉบับร่างที่ user เป็นผู้สร้าง."""
    return or_(
        LegalCase.blind_published.is_(True),
        LegalCase.created_by_user_id == current_user.id,
    )


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
        .filter(_visible_cases_filter(current_user))
        .order_by(dist)
        .limit(VECTOR_CANDIDATE_LIMIT)
        .all()
    )

    scored = []
    for r in candidates:
        if r.embedding is None or not can_list_document(current_user, r):
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
        can_ub = can_view_unblinded(current_user, r)
        results.append(
            {
                "id": r.id,
                "casetype": r.casetype,
                "event_date": r.event_date,
                "blind_published": bool(r.blind_published),
                "similarity": round(sim, 4),
                "similarity_percent": round(sim * 100, 2),
                "doc_path": doc_path_for_api(current_user, r),
                "redacted_doc_path": r.redacted_doc_path,
                "can_view_unblinded": can_ub,
                "embedding_source_text": r.embedding_source_text if can_ub else None,
            }
        )

    return {
        "results": results,
        "count": len(results),
        "min_similarity": MIN_COSINE_SIMILARITY,
    }
