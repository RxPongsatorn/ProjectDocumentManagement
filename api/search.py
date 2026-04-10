import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import get_current_user
from app.document_access import can_view_unblinded, has_public_blinded_copy, is_admin
from app.embedded_text import embed_query
from app.models import LegalCase, User
router = APIRouter(prefix="/search", tags=["search"])
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
    query = (
        db.query(LegalCase)
        .filter(LegalCase.embedding.isnot(None))
        .order_by(dist)
        .limit(VECTOR_CANDIDATE_LIMIT)
    )
    if not is_admin(current_user):
        query = query.filter(LegalCase.redacted_doc_path.isnot(None)).filter(
            LegalCase.redacted_doc_path != ""
        )
    candidates = query.all()
    scored = []
    for r in candidates:
        if r.embedding is None:
            continue
        sim = _cosine_similarity(qv, list(r.embedding))
        if sim <= MIN_COSINE_SIMILARITY:
            continue
        can_ub = can_view_unblinded(current_user, r)
        if not can_ub and not has_public_blinded_copy(r):
            continue
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
                "similarity": round(sim, 4),
                "similarity_percent": round(sim * 100, 2),
                "doc_path": r.doc_path if can_ub else r.redacted_doc_path,
                "redacted_doc_path": r.redacted_doc_path,
                "can_view_unblinded": can_ub,
                "variant_shown": "unblinded" if can_ub else "blinded",
                "embedding_source_text": r.embedding_source_text if can_ub else None,
            }
        )
    return {
        "results": results,
        "count": len(results),
        "min_similarity": MIN_COSINE_SIMILARITY,
    }
