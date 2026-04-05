"""
สคริปต์ทดลอง FAISS + MiniLM — ตรรกะ NLP หลักของระบบจริงอยู่ที่ app/nlp_processor.py
(embedding โปรดักชันใช้ E5 768 มิติผ่าน app.embedded_text)
"""
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
import re

# ===== Embedding =====
from sentence_transformers import SentenceTransformer

# ===== Vector DB (FAISS) =====
import faiss
import numpy as np


# =========================
# 1. Data Schema
# =========================
@dataclass
class CaseData:
    victim_name: str
    suspect_name: str
    event_date: str
    fact_summary: str
    legal_basis: str
    prosecutor_opinion: str
    filename: str = "-"
    casetype: str = "-"
    bank_account: str = "-"
    id_card: str = "-"
    plate_number: str = "-"


# =========================
# 2. NLP Processor (Expanded Rule-base & Compression)
# =========================
class NLPProcessor:

    def __init__(self):
        # 1. หมวดคีย์เวิร์ดสำหรับจัดกลุ่ม
        self.violence_keywords = ["ชก", "ต่อย", "ตี", "ทำร้าย", "ผลัก", "แทง", "ตบ", "ดึงผม", "ดึง", "เตะ", "กระทืบ", "ทุบ", "ฟัน", "ยิง"]
        self.injury_keywords = ["หัก", "เลือดออก", "บาดเจ็บ", "ล้ม", "ฟกช้ำ", "ร้าว", "สาหัส", "ตาย", "เสียชีวิต", "ฉีกขาด"]
        self.weapon_keywords = ["ปืน", "มีด", "ขวดแก้ว", "ไม้", "เหล็ก", "สนับมือ", "อาวุธ"]
        self.drug_keywords = ["ยาบ้า", "ไอซ์", "ยาเสพติด", "เฮโรอีน", "เสพ", "ครอบครอง", "จำหน่าย", "ซุกซ่อน"]
        self.theft_keywords = ["ลักทรัพย์", "ขโมย", "งัดแงะ", "ขโมยของ", "ปล้น", "ชิงทรัพย์", "วิ่งราว"]
        self.fraud_keywords = ["ฉ้อโกง", "หลอกลวง", "โอนเงิน", "แชร์ลูกโซ่", "ปลอมแปลง", "มิจฉาชีพ", "หลอก"]

        # 2. คำฟุ่มเฟือย/คำทางกฎหมายทั่วไปที่ต้อง "ตัดทิ้ง" (Stop-words) เพื่อเอาแค่เนื้อหาสำคัญ
        self.stop_words = [
            "ผู้ต้องหาได้", "ผู้ต้องหา", "ผู้เสียหาย", "จำเลย", "โจทก์",
            "บริเวณ", "ภายใน", "ทำให้", "ได้รับ", "จำนวนมาก", "เกิดความ",
            "เหตุเกิดที่", "ส่งผลให้", "เป็นเหตุให้", "กระทำการ", "ถูก",
            "เจ้าหน้าที่ตำรวจ", "เข้าตรวจค้น", "ของกลาง", "รับสารภาพว่า",
            "อย่าง", "และ", "หรือ", "ด้วย", "ไป", "มา"
        ]

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def compress_text(self, text: str) -> str:
        """ฟังก์ชันสำหรับตัดคำฟุ่มเฟือย เหลือแต่แก่นของเหตุการณ์"""
        compressed = text
        for word in self.stop_words:
            # แทนที่คำฟุ่มเฟือยด้วยช่องว่าง
            compressed = compressed.replace(word, "")
        
        # จัดการช่องว่างที่อาจเกิดขึ้นจากการตัดคำ
        return self.clean_text(compressed)

    def extract_keywords(self, text: str) -> Dict:
        print("    [Step 1.2] Extracting Keywords (ดึงหมวดหมู่หลัก)...")
        extracted = {
            "actions": [w for w in self.violence_keywords if w in text],
            "injuries": [w for w in self.injury_keywords if w in text],
            "weapons": [w for w in self.weapon_keywords if w in text],
            "drugs": [w for w in self.drug_keywords if w in text],
            "thefts": [w for w in self.theft_keywords if w in text],
            "frauds": [w for w in self.fraud_keywords if w in text]
        }
        
        for category, words in extracted.items():
            if words:
                print(f"      - พบ {category}: {words}")
                
        return extracted

    def normalize(self, keywords: Dict) -> List[str]:
        normalized = []
        if keywords["actions"]: normalized.append("คดีทำร้ายร่างกาย")
        if keywords["injuries"]: normalized.append("บาดเจ็บ")
        if keywords["weapons"]: normalized.append("ใช้อาวุธ")
        if keywords["drugs"]: normalized.append("คดียาเสพติด")
        if keywords["thefts"]: normalized.append("คดีเกี่ยวกับทรัพย์")
        if keywords["frauds"]: normalized.append("คดีฉ้อโกง")
        return normalized

    def build_embedding_text(self, case: CaseData) -> str:
        print(f"  [Step 1] เริ่ม NLP Processing สำหรับไฟล์: {case.filename}")
        
        # คลีนข้อความตั้งต้น
        original_text = self.clean_text(case.fact_summary)
        print(f"    [Step 1.1] ข้อความเดิม: '{original_text}'")

        # กรองเฉพาะเนื้อหาสำคัญ (ตัดคำฟุ่มเฟือย)
        compressed_text = self.compress_text(original_text)
        print(f"    [Step 1.1.5] 👉 ข้อความที่กรองแล้ว: '{compressed_text}'")

        # ดึงหมวดหมู่ (ใช้ข้อความดั้งเดิมเพื่อไม่ให้คีย์เวิร์ดบางตัวตกหล่นตอนกรอง)
        extracted = self.extract_keywords(original_text)
        normalized = self.normalize(extracted)

        # รวมฟิลด์สำคัญเพื่อสร้าง Text สำหรับนำไปทำ Embedding
        # สังเกตว่าเราใช้ compressed_text แทน fact_summary เต็มๆ แล้ว
        parts = [
            compressed_text,
            case.legal_basis,
            " ".join(normalized)
        ]

        final_text = " ".join([p for p in parts if p])
        print(f"    [Step 1.3] Final Text สำหรับเข้า Model:\n      '{final_text}'")
        return final_text


# =========================
# 3. Vector Store (FAISS)
# =========================
class VectorStore:

    def __init__(self, dim: int):
        self.index = faiss.IndexFlatL2(dim)
        self.metadata = []

    def add(self, vector: np.ndarray, meta: dict):
        self.index.add(np.array([vector]).astype("float32"))
        self.metadata.append(meta)

    def search(self, vector: np.ndarray, k=3):
        D, I = self.index.search(np.array([vector]).astype("float32"), k)
        results = []
        for i, idx in enumerate(I[0]):
            if idx < len(self.metadata):
                results.append({
                    "distance": D[0][i],
                    "metadata": self.metadata[idx]
                })
        return results


# =========================
# 4. Pipeline
# =========================
class CasePipeline:

    def __init__(self):
        print(">> กำลังโหลด Model NLP (SentenceTransformer)...")
        self.nlp = NLPProcessor()
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.vector_store = VectorStore(dim=384)
        print(">> โหลด Model เสร็จสิ้น เตรียมพร้อมทำงาน!\n")

    def ingest(self, case: CaseData):
        print(f"{'='*50}")
        print(f"📥 INGESTING: {case.filename}")
        
        embedding_text = self.nlp.build_embedding_text(case)

        print(f"  [Step 2] แปลง Text เป็น Vector (Embedding)...")
        vector = self.model.encode(embedding_text)

        print(f"  [Step 3] บันทึก Vector และ Metadata ลง FAISS DB...")
        self.vector_store.add(vector, asdict(case))
        print(f"✅ บันทึกสำเร็จ\n")

    def ingest_batch(self, cases_data: List[Dict]):
        print(f"🚀 เริ่มกระบวนการ Ingest ข้อมูลจำนวน {len(cases_data)} รายการ...\n")
        for data in cases_data:
            case = CaseData(**data)
            self.ingest(case)

    def search(self, query: str, k=3):
        print(f"{'='*50}")
        print(f"🔎 SEARCHING QUERY: '{query}'")
        
        # กรอง Query แบบเดียวกับตอน Ingest เพื่อให้รูปแบบภาษาตรงกัน
        compressed_query = self.nlp.compress_text(query)
        print(f"  [Search Step] ปรับ Query เป็น: '{compressed_query}'")
        
        vector = self.model.encode(compressed_query)
        results = self.vector_store.search(vector, k=k)
        
        print(f"✅ พบผลลัพธ์ {len(results)} รายการ:")
        for i, r in enumerate(results, 1):
            meta = r['metadata']
            print(f"  [{i}] Score(L2): {r['distance']:.4f} | ไฟล์: {meta['filename']}")
            print(f"      ผู้ต้องหา: {meta['suspect_name']}")
            print(f"      สรุปเหตุการณ์: {meta['fact_summary']}")
        print(f"{'='*50}\n")
        return results


# =========================
# 5. Example Usage
# =========================
if __name__ == "__main__":
    pipeline = CasePipeline()

    batch_data = [
        {
            "victim_name": "นายชัยวัฒน์ พรหมดี",
            "suspect_name": "นายอัครเดช มั่นคง",
            "event_date": "2026-02-18",
            "fact_summary": "ผู้ต้องหาได้ใช้ขวดแก้วตีผู้เสียหายบริเวณศีรษะ ภายในร้านอาหาร หลังเกิดความไม่พอใจเรื่องการพูดจา ทำให้ผู้เสียหายได้รับบาดเจ็บเลือดออกจำนวนมาก",
            "legal_basis": "ความผิดฐานทำร้ายร่างกายโดยใช้อาวุธ ตามประมวลกฎหมายอาญา มาตรา 295",
            "prosecutor_opinion": "ควรสั่งฟ้อง เนื่องจากมีพยานแวดล้อมและหลักฐานวัตถุพยานชัดเจน",
            "filename": "assault_case_005.pdf",
            "casetype": "คดีอาญา",
        },
        {
            "victim_name": "นางสาวสมศรี มั่งมี",
            "suspect_name": "นายหัวขโมย ย่องเบา",
            "event_date": "2026-04-02",
            "fact_summary": "ผู้ต้องหาได้งัดแงะหน้าต่างบ้านของผู้เสียหายในเวลากลางคืน และได้ขโมยโทรศัพท์มือถือและเงินสดจำนวน 10,000 บาท หลบหนีไป",
            "legal_basis": "ความผิดฐานลักทรัพย์ในเวลากลางคืน",
            "prosecutor_opinion": "สั่งฟ้อง",
            "filename": "theft_case_001.pdf",
            "casetype": "คดีอาญา",
        }
    ]

    # นำเข้าข้อมูล
    pipeline.ingest_batch(batch_data)

    # 🔍 ทดสอบค้นหา (ตอนค้นหาก็จะถูกตัดคำให้กระชับด้วยเช่นกัน)
    pipeline.search("ผู้ต้องหาเอาขวดตีหัวผู้เสียหายในร้านจนเลือดออก", k=1)