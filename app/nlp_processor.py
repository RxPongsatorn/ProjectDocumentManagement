from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CaseData:
    victim_name: str
    suspect_name: str
    event_date: str
    fact_summary: str
    legal_basis: str
    prosecutor_opinion: str
    filename: Optional[str] = None
    casetype: Optional[str] = None
    bank_account: Optional[str] = None
    id_card: Optional[str] = None
    plate_number: Optional[str] = None

    @classmethod
    def from_extraction(cls, d: dict) -> "CaseData":
        """Map dict from classify_text / JSON body to CaseData."""
        return cls(
            victim_name=(d.get("victim_name") or "") or "",
            suspect_name=(d.get("suspect_name") or "") or "",
            event_date=(d.get("event_date") or "") or "",
            fact_summary=(d.get("fact_summary") or "") or "",
            legal_basis=(d.get("legal_basis") or "") or "",
            prosecutor_opinion=(d.get("prosecutor_opinion") or "") or "",
            filename=d.get("filename"),
            casetype=(d.get("casetype") or d.get("case_type") or None) or None,
            bank_account=d.get("bank_account"),
            id_card=d.get("id_card"),
            plate_number=d.get("plate_number"),
        )


class NLPProcessor:
    """
    ตรรกะเดียวกับ api/vector_test.py: กัดจับคีย์เวิร์ดหมวดหมู่ + ตัดคำฟุ่มเฟือย
    ก่อนสร้างข้อความเข้า embedding (ไม่ใส่ชื่อบุคคลในเวกเตอร์ — ลด noise/PII)
    """

    def __init__(self):
        self.violence_keywords = [
            "ชก", "ต่อย", "ตี", "ทำร้าย", "ผลัก", "แทง", "ตบ", "ดึงผม", "ดึง",
            "เตะ", "กระทืบ", "ทุบ", "ฟัน", "ยิง",
        ]
        self.injury_keywords = [
            "หัก", "เลือดออก", "บาดเจ็บ", "ล้ม", "ฟกช้ำ", "ร้าว", "สาหัส",
            "ตาย", "เสียชีวิต", "ฉีกขาด",
        ]
        self.weapon_keywords = [
            "ปืน", "มีด", "ขวดแก้ว", "ไม้", "เหล็ก", "สนับมือ", "อาวุธ",
        ]
        self.drug_keywords = [
            "ยาบ้า", "ไอซ์", "ยาเสพติด", "เฮโรอีน", "เสพ", "ครอบครอง",
            "จำหน่าย", "ซุกซ่อน",
        ]
        self.theft_keywords = [
            "ลักทรัพย์", "ขโมย", "งัดแงะ", "ขโมยของ", "ปล้น", "ชิงทรัพย์", "วิ่งราว",
        ]
        self.fraud_keywords = [
            "ฉ้อโกง", "หลอกลวง", "โอนเงิน", "แชร์ลูกโซ่", "ปลอมแปลง",
            "มิจฉาชีพ", "หลอก",
        ]

        self.stop_words = [
            "ผู้ต้องหาได้", "ผู้ต้องหา", "ผู้เสียหาย", "จำเลย", "โจทก์",
            "บริเวณ", "ภายใน", "ทำให้", "ได้รับ", "จำนวนมาก", "เกิดความ",
            "เหตุเกิดที่", "ส่งผลให้", "เป็นเหตุให้", "กระทำการ", "ถูก",
            "เจ้าหน้าที่ตำรวจ", "เข้าตรวจค้น", "ของกลาง", "รับสารภาพว่า",
            "อย่าง", "และ", "หรือ", "ด้วย", "ไป", "มา",
        ]
        # ตัดวลียาวก่อน ลดโอกาสตัดผิดพลาดจากคำย่อย
        self._stop_words_sorted = sorted(self.stop_words, key=len, reverse=True)

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "")
        return text.strip()

    def compress_text(self, text: str) -> str:
        """ตัดคำฟุ่มเฟือย เหลือแก่นเหตุการณ์ (ใช้ทั้งตอน ingest และ query)"""
        compressed = text or ""
        for word in self._stop_words_sorted:
            if word:
                compressed = compressed.replace(word, " ")
        return self.clean_text(compressed)

    def extract_keywords(self, text: str) -> Dict[str, List[str]]:
        """ดึงคีย์เวิร์ดจากข้อความต้นฉบับ (หลัง clean) — ไม่ใช้ข้อความที่ compress แล้ว เพื่อไม่ให้คีย์หลุด"""
        return {
            "actions": [w for w in self.violence_keywords if w in text],
            "injuries": [w for w in self.injury_keywords if w in text],
            "weapons": [w for w in self.weapon_keywords if w in text],
            "drugs": [w for w in self.drug_keywords if w in text],
            "thefts": [w for w in self.theft_keywords if w in text],
            "frauds": [w for w in self.fraud_keywords if w in text],
        }

    def normalize(self, keywords: Dict[str, List[str]]) -> List[str]:
        normalized: List[str] = []
        if keywords.get("actions"):
            normalized.append("คดีทำร้ายร่างกาย")
        if keywords.get("injuries"):
            normalized.append("บาดเจ็บ")
        if keywords.get("weapons"):
            normalized.append("ใช้อาวุธ")
        if keywords.get("drugs"):
            normalized.append("คดียาเสพติด")
        if keywords.get("thefts"):
            normalized.append("คดีเกี่ยวกับทรัพย์")
        if keywords.get("frauds"):
            normalized.append("คดีฉ้อโกง")
        return normalized

    def build_embedding_text(self, case: CaseData) -> str:
        """
        เหมือน vector_test: compressed fact + ฐานกฎหมาย + ป้ายกลุ่มจากคีย์เวิร์ด
        ไม่ใส่ชื่อ/วันที่ — ข้อมูลสะอาดขึ้นสำหรับเวกเตอร์
        """
        original_text = self.clean_text(case.fact_summary)
        extracted = self.extract_keywords(original_text)
        compressed_text = self.compress_text(original_text)
        normalized = self.normalize(extracted)

        parts = [
            compressed_text,
            (case.casetype or "").strip(),
            (case.legal_basis or "").strip(),
            " ".join(normalized),
        ]
        return " ".join(p for p in parts if p).strip()

    def preprocess_query_for_search(self, query: str) -> str:
        """ให้รูปแบบ query ใกล้เคียงข้อความตอน ingest (เหมือน vector_test.search)"""
        cleaned = self.clean_text(query)
        compressed = self.compress_text(cleaned)
        return compressed if compressed else cleaned
