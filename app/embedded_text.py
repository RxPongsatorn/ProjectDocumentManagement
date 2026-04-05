from sentence_transformers import SentenceTransformer

from app.nlp_processor import CaseData, NLPProcessor

# intfloat/multilingual-e5-base → 768 dims (matches LegalCase.embedding / pgvector)
EMBEDDING_DIM = 768

_nlp = NLPProcessor()
model = SentenceTransformer("intfloat/multilingual-e5-base")


def build_search_text(d: dict) -> str:
    """
    Text fed into the embedding model for indexing (same logic as api/vector_services NLP pipeline).
    """
    return _nlp.build_embedding_text(CaseData.from_extraction(d))


def embed_text(text: str) -> list:
    """Embed a document/passage for storage in pgvector (E5 passage prefix)."""
    if not (text or "").strip():
        text = ""
    return model.encode(f"passage: {text}").tolist()


def embed_query(text: str) -> list:
    """Embed a user search query (E5 query prefix — use in /search, not for stored vectors)."""
    if not (text or "").strip():
        text = ""
    return model.encode(f"query: {text}").tolist()
