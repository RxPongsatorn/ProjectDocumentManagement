from sentence_transformers import SentenceTransformer
from app.nlp_processor import CaseData, NLPProcessor
EMBEDDING_DIM = 768
_nlp = NLPProcessor()
model = SentenceTransformer("intfloat/multilingual-e5-base")
def build_search_text(d: dict) -> str:
    return _nlp.build_embedding_text(CaseData.from_extraction(d))
def embed_text(text: str) -> list:
    if not (text or "").strip():
        text = ""
    return model.encode(f"passage: {text}").tolist()
def embed_query(text: str) -> list:
    if not (text or "").strip():
        return model.encode("query: ").tolist()
    q = _nlp.preprocess_query_for_search(text)
    return model.encode(f"query: {q}").tolist()
