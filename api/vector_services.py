"""
ตัวอย่าง pipeline เดียวกับระบบจริง (NLP → ข้อความสำหรับ embed → vector)
- โปรดักชัน: app.embedded_text + pgvector ใน LegalCase.embedding
- ไฟล์นี้แสดง pattern เดียวกัน แบบ in-memory FAISS (768 มิติ = multilingual-e5-base)
"""
from typing import List

import faiss
import numpy as np

from app.embedded_text import EMBEDDING_DIM, embed_query, embed_text
from app.nlp_processor import CaseData, NLPProcessor


class VectorStore:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatL2(dim)
        self.metadata: List[dict] = []

    def add(self, vector: List[float], meta: dict) -> None:
        arr = np.array([vector], dtype="float32")
        self.index.add(arr)
        self.metadata.append(meta)

    def search(self, vector: List[float], k: int = 3) -> List[dict]:
        arr = np.array([vector], dtype="float32")
        _, indices = self.index.search(arr, k)
        out: List[dict] = []
        for idx in indices[0]:
            if 0 <= idx < len(self.metadata):
                out.append(self.metadata[idx])
        return out


class CasePipeline:
    """
    Ingest/search ด้วยข้อความ embedding เดียวกับ process_case_text (NLPProcessor + E5 passage/query).
    """

    def __init__(self):
        self.nlp = NLPProcessor()
        self.vector_store = VectorStore(dim=EMBEDDING_DIM)

    def ingest(self, case: CaseData) -> None:
        embedding_text = self.nlp.build_embedding_text(case)
        vector = embed_text(embedding_text)
        self.vector_store.add(
            vector,
            {
                "victim": case.victim_name,
                "suspect": case.suspect_name,
                "summary": case.fact_summary,
                "law": case.legal_basis,
            },
        )

    def ingest_from_dict(self, d: dict) -> None:
        self.ingest(CaseData.from_extraction(d))

    def search(self, query: str, k: int = 3) -> List[dict]:
        vector = embed_query(query)
        return self.vector_store.search(vector, k=k)


if __name__ == "__main__":
    pipeline = CasePipeline()

    case = CaseData(
        victim_name="นาย B",
        suspect_name="นาย A",
        event_date="2026-03-20",
        fact_summary="ผู้ต้องหาชกต่อยผู้เสียหายในร้านอาหารจนฟันหักและเลือดออก",
        legal_basis="ประมวลกฎหมายอาญา มาตรา 295",
        prosecutor_opinion="ควรสั่งฟ้อง",
    )

    pipeline.ingest(case)

    results = pipeline.search("ตีคนจนบาดเจ็บฟันหัก")
    print("\nSearch results:")
    for r in results:
        print(r)
