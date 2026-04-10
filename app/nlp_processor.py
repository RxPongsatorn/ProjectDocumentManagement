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
    def __init__(self):
        self.violence_keywords = [
            "ชกต่อย",
            "ขู่",
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
            "ใช้กำลัง",
            "หลังเกิด", "หลังจาก", "เนื่องจาก", "เพราะ", "เพื่อ",
            "จนได้รับ", "จนได้", "จน", "ได้รับ", "จากการ", "จาก", "การ",
            "เล็กน้อย", "เพียง", "แค่", "ซึ่ง", "ว่า", "โดย",
            "ผู้ต้องหาได้", "ผู้ต้องหา", "ผู้เสียหาย", "จำเลย", "โจทก์",
            "บริเวณ", "ภายใน", "ทำให้", "ได้รับ", "จำนวนมาก", "เกิดความ",
            "เหตุเกิดที่", "ส่งผลให้", "เป็นเหตุให้", "กระทำการ", "ถูก",
            "เจ้าหน้าที่ตำรวจ", "เข้าตรวจค้น", "ของกลาง", "รับสารภาพว่า",
            "อย่าง", "และ", "หรือ", "ด้วย", "ไป", "มา",
        ]
        self._stop_words_sorted = sorted(self.stop_words, key=len, reverse=True)
    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "")
        return text.strip()
    def compress_text(self, text: str) -> str:
        compressed = text or ""
        for word in self._stop_words_sorted:
            if word:
                compressed = compressed.replace(word, " ")
        return self.clean_text(compressed)
    def extract_keywords(self, text: str) -> Dict[str, List[str]]:
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
    def _combine_actions(self, actions: List[str]) -> str:
        s = set(actions or [])
        if "ชกต่อย" in s or ("ชก" in s and "ต่อย" in s):
            s.discard("ชก")
            s.discard("ต่อย")
            s.add("ชกต่อย")
        return " ".join(sorted(s))
    def _extract_motives(self, text: str) -> List[str]:
        t = self.clean_text(text)
        out: List[str] = []
        for m in re.finditer(r"(เรื่อง[^,\\.]{1,40})", t):
            phrase = m.group(1).strip()
            phrase = re.split(r"(ส่งผลให้|ทำให้|จน|เป็นเหตุให้)", phrase)[0].strip()
            if phrase and phrase not in out:
                out.append(phrase)
        for m in re.finditer(r"(โต้เถียง|ทะเลาะ|มีปากเสียง)([^,\\.]{1,40})", t):
            phrase = (m.group(2) or "").strip()
            phrase = re.split(r"(ส่งผลให้|ทำให้|จน|เป็นเหตุให้)", phrase)[0].strip()
            phrase = phrase.strip(" :;")
            if phrase:
                if "เรื่อง" not in phrase and len(phrase) <= 40:
                    phrase = phrase
                if phrase and phrase not in out:
                    out.append(phrase)
        return out
    def _extract_locations(self, text: str) -> List[str]:
        t = self.clean_text(text)
        out: List[str] = []
        for m in re.finditer(r"(ใน[^,\\.]{1,25})", t):
            phrase = m.group(1).strip()
            phrase = re.split(r"(หลัง|เนื่องจาก|เพราะ|เพื่อ|ส่งผลให้|ทำให้|จน|เป็นเหตุให้)", phrase)[0].strip()
            phrase = phrase.strip(" :;")
            if phrase and phrase not in out:
                out.append(phrase)
        return out
    def _build_weapon_phrase(self, extracted: Dict[str, List[str]]) -> str:
        weapons = sorted(set(extracted.get("weapons", [])))
        actions = set(extracted.get("actions", []))
        if not weapons:
            return ""
        if "มีด" in weapons and "ขู่" in actions:
            return "ใช้อาวุธมีดขู่"
        return "ใช้อาวุธ" + "".join(weapons)
    def summarize_fact_for_embedding(self, fact_summary: str) -> str:
        original = self.clean_text(fact_summary)
        if not original:
            return ""
        extracted = self.extract_keywords(original)
        actions_list = extracted.get("actions", [])
        weapon_phrase = self._build_weapon_phrase(extracted)
        if weapon_phrase and "ขู่" in actions_list:
            actions_list = [a for a in actions_list if a != "ขู่"]
        actions = self._combine_actions(actions_list)
        injuries = " ".join(sorted(set(extracted.get("injuries", []))))
        motives = " ".join(self._extract_motives(original))
        locations = " ".join(self._extract_locations(original))
        compressed = self.compress_text(original)
        fallback = ""
        if not motives and not locations:
            fallback = " ".join(compressed.split()[:12])
        parts = [
            actions,
            weapon_phrase,
            locations,
            motives or fallback,
            injuries,
        ]
        return " ".join([p for p in parts if p]).strip()
    def build_embedding_text(self, case: CaseData) -> str:
        original_text = self.clean_text(case.fact_summary)
        extracted = self.extract_keywords(original_text)
        normalized = self.normalize(extracted)
        summarized_fact = self.summarize_fact_for_embedding(original_text)
        parts = [
            summarized_fact,
            (case.casetype or "").strip(),
            (case.legal_basis or "").strip(),
            " ".join(normalized),
        ]
        return " ".join(p for p in parts if p).strip()
    def preprocess_query_for_search(self, query: str) -> str:
        cleaned = self.clean_text(query)
        summarized = self.summarize_fact_for_embedding(cleaned)
        return summarized if summarized else self.compress_text(cleaned) or cleaned
