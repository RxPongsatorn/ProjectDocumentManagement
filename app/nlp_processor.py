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
    def __init__(self):
        self.violence_keywords = ["ชก", "ต่อย", "ตี", "ทำร้าย", "ผลัก", "แทง"]
        self.injury_keywords = ["หัก", "เลือดออก", "บาดเจ็บ", "ล้ม"]

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "")
        return text.strip()

    def extract_keywords(self, text: str) -> Dict:
        actions = []
        injuries = []

        for word in self.violence_keywords:
            if word in text:
                actions.append(word)

        for word in self.injury_keywords:
            if word in text:
                injuries.append(word)

        return {
            "actions": list(set(actions)),
            "injuries": list(set(injuries)),
        }

    def normalize(self, keywords: Dict) -> List[str]:
        normalized = []

        if keywords["actions"]:
            normalized.append("ทำร้ายร่างกาย")

        if keywords["injuries"]:
            normalized.append("บาดเจ็บ")

        return normalized

    def build_embedding_text(self, case: CaseData) -> str:
        text = self.clean_text(case.fact_summary)

        extracted = self.extract_keywords(text)
        normalized = self.normalize(extracted)

        parts = [
            case.casetype or "",
            case.victim_name,
            case.suspect_name,
            case.event_date,
            text,
            case.legal_basis,
            case.prosecutor_opinion,
            " ".join(normalized),
        ]

        return " ".join([p for p in parts if p]).strip()
