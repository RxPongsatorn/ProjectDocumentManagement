import pdfplumber
from pythainlp.util import normalize
def extract_text_from_pdf(pdf_path: str) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
    return "\n".join(texts).strip()
def normalize_thai_text(text: str) -> str:
    text = normalize(text)
    text = text.replace("\xa0", " ")
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()