from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pythainlp import word_tokenize
from pythainlp.tag import tag_provinces

_TOKEN_ENGINE = os.environ.get("PYTHAINLP_TOKEN_ENGINE", "newmm")
_KEY_CATEGORIES = ("actions", "injuries", "weapons", "drugs", "thefts", "frauds")


def _load_keyword_data() -> Dict[str, Any]:
    path = Path(__file__).resolve().parent / "nlp_keyword_data.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _empty_keyword_dict() -> Dict[str, List[str]]:
    return {k: [] for k in _KEY_CATEGORIES}


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
    """
    Thai legal text: PyThaiNLP tokenization + stopword filtering,
    province dictionary for locations, structured prefixes for embeddings.
    """

    _MOTIVE_SPLIT_RE = re.compile(
        r"(\u0e2a\u0e48\u0e07\u0e1c\u0e25\u0e43\u0e2b\u0e49|\u0e17\u0e33\u0e43\u0e2b\u0e49|\u0e08\u0e19|\u0e40\u0e1b\u0e47\u0e19\u0e40\u0e2b\u0e15\u0e38\u0e43\u0e2b\u0e49)"
    )
    _LOC_SPLIT_RE = _MOTIVE_SPLIT_RE

    def __init__(self) -> None:
        self._data = _load_keyword_data()
        self._token_engine = _TOKEN_ENGINE
        self.violence_keywords = list(self._data["violence_keywords"])
        self.injury_keywords = list(self._data["injury_keywords"])
        self.weapon_keywords = list(self._data["weapon_keywords"])
        self.drug_keywords = list(self._data["drug_keywords"])
        self.theft_keywords = list(self._data["theft_keywords"])
        self.fraud_keywords = list(self._data["fraud_keywords"])
        self.stop_words = list(self._data["stop_words"])
        self._location_spurious = frozenset(self._data["location_spurious"])
        self._normalize_labels: Dict[str, str] = dict(self._data["normalize_labels"])
        self._pfx: Dict[str, str] = dict(self._data["section_prefixes"])
        self._prepare_stopword_removal()
        self._prepare_keyword_sequences()

    def _prepare_stopword_removal(self) -> None:
        singles: set[str] = set()
        phrases: List[List[str]] = []
        e = self._token_engine
        for sw in self.stop_words:
            s = (sw or "").strip()
            if not s:
                continue
            toks = word_tokenize(s, engine=e)
            if len(toks) <= 1:
                singles.add(toks[0] if toks else s)
            else:
                phrases.append(toks)
        phrases.sort(key=len, reverse=True)
        self._stop_tokens_exact = singles
        self._stop_phrase_sequences = phrases

    def _prepare_keyword_sequences(self) -> None:
        e = self._token_engine

        def pairs(words: List[str]) -> List[Tuple[str, List[str]]]:
            out: List[Tuple[str, List[str]]] = []
            for w in words:
                seq = word_tokenize(w, engine=e)
                out.append((w, seq if seq else [w]))
            return out

        self._violence_kw_pairs = pairs(self.violence_keywords)
        self._injury_kw_pairs = pairs(self.injury_keywords)
        self._weapon_kw_pairs = pairs(self.weapon_keywords)
        self._drug_kw_pairs = pairs(self.drug_keywords)
        self._theft_kw_pairs = pairs(self.theft_keywords)
        self._fraud_kw_pairs = pairs(self.fraud_keywords)

    @staticmethod
    def _tokens_match_subsequence(haystack: List[str], needle: List[str]) -> bool:
        if not needle or not haystack or len(needle) > len(haystack):
            return False
        for i in range(len(haystack) - len(needle) + 1):
            if haystack[i : i + len(needle)] == needle:
                return True
        return False

    def _remove_stop_tokens(self, tokens: List[str]) -> List[str]:
        if not tokens:
            return []
        i = 0
        out: List[str] = []
        while i < len(tokens):
            matched = False
            for seq in self._stop_phrase_sequences:
                end = i + len(seq)
                if end <= len(tokens) and tokens[i:end] == seq:
                    i = end
                    matched = True
                    break
            if matched:
                continue
            tok = tokens[i]
            if tok not in self._stop_tokens_exact:
                out.append(tok)
            i += 1
        return out

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "")
        return text.strip()

    def compress_text(self, text: str) -> str:
        t = self.clean_text(text)
        if not t:
            return ""
        tokens = word_tokenize(t, engine=self._token_engine)
        filtered = self._remove_stop_tokens(tokens)
        return self.clean_text(" ".join(filtered))

    def _extract_keywords_from_tokens(self, tokens: List[str]) -> Dict[str, List[str]]:
        if not tokens:
            return _empty_keyword_dict()

        def pick(pairs: List[Tuple[str, List[str]]]) -> List[str]:
            seen: set[str] = set()
            hit: List[str] = []
            for label, seq in pairs:
                if self._tokens_match_subsequence(tokens, seq) and label not in seen:
                    seen.add(label)
                    hit.append(label)
            return hit

        return {
            "actions": pick(self._violence_kw_pairs),
            "injuries": pick(self._injury_kw_pairs),
            "weapons": pick(self._weapon_kw_pairs),
            "drugs": pick(self._drug_kw_pairs),
            "thefts": pick(self._theft_kw_pairs),
            "frauds": pick(self._fraud_kw_pairs),
        }

    def extract_keywords(self, text: str) -> Dict[str, List[str]]:
        t = self.clean_text(text)
        if not t:
            return _empty_keyword_dict()
        tokens = word_tokenize(t, engine=self._token_engine)
        return self._extract_keywords_from_tokens(tokens)

    def normalize(self, keywords: Dict[str, List[str]]) -> List[str]:
        normalized: List[str] = []
        if keywords.get("actions"):
            normalized.append(self._normalize_labels["actions"])
        if keywords.get("injuries"):
            normalized.append(self._normalize_labels["injuries"])
        if keywords.get("weapons"):
            normalized.append(self._normalize_labels["weapons"])
        if keywords.get("drugs"):
            normalized.append(self._normalize_labels["drugs"])
        if keywords.get("thefts"):
            normalized.append(self._normalize_labels["thefts"])
        if keywords.get("frauds"):
            normalized.append(self._normalize_labels["frauds"])
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
        for m in re.finditer(r"(\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07[^,\\.]{1,40})", t):
            phrase = m.group(1).strip()
            phrase = self._MOTIVE_SPLIT_RE.split(phrase)[0].strip()
            if phrase and phrase not in out:
                out.append(phrase)
        motive2 = (
            r"(\u0e42\u0e15\u0e49\u0e40\u0e16\u0e35\u0e22\u0e07|"
            r"\u0e17\u0e30\u0e40\u0e25\u0e32\u0e30|"
            r"\u0e21\u0e35\u0e1b\u0e32\u0e01\u0e40\u0e2a\u0e35\u0e22\u0e07)([^,\\.]{1,40})"
        )
        for m in re.finditer(motive2, t):
            phrase = (m.group(2) or "").strip()
            phrase = self._MOTIVE_SPLIT_RE.split(phrase)[0].strip()
            phrase = phrase.strip(" :;")
            if phrase and phrase not in out:
                out.append(phrase)
        return out

    def _is_spurious_location_phrase(self, phrase: str) -> bool:
        p = phrase.strip()
        for bad in self._location_spurious:
            if p == bad or p.startswith(bad) or bad in p:
                return True
        return False

    def _locations_from_provinces(self, tokens: List[str]) -> List[str]:
        tagged = tag_provinces(tokens)
        out: List[str] = []
        seen: set[str] = set()
        for tok, tag in tagged:
            if tag == "B-LOCATION" and tok not in seen:
                seen.add(tok)
                out.append(tok)
        return out

    def _extract_locations_regex(self, text: str) -> List[str]:
        t = self.clean_text(text)
        out: List[str] = []
        seen: set[str] = set()
        for m in re.finditer(r"(\u0e43\u0e19[^,\\.]{1,25})", t):
            phrase = m.group(1).strip()
            phrase = self._LOC_SPLIT_RE.split(phrase)[0].strip()
            phrase = phrase.strip(" :;")
            if not phrase or phrase in seen:
                continue
            if self._is_spurious_location_phrase(phrase):
                continue
            seen.add(phrase)
            out.append(phrase)
        return out

    def _merge_locations(self, provinces: List[str], regex_locs: List[str]) -> str:
        ordered: List[str] = []
        seen: set[str] = set()
        for p in provinces + regex_locs:
            key = p.strip()
            if key and key not in seen:
                seen.add(key)
                ordered.append(key)
        return " ".join(ordered)

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
        tokens = word_tokenize(original, engine=self._token_engine)
        extracted = self._extract_keywords_from_tokens(tokens)
        return self._summarize_fact_core(original, tokens, extracted)

    def _summarize_fact_core(
        self,
        original: str,
        tokens: List[str],
        extracted: Dict[str, List[str]],
    ) -> str:
        actions_list = list(extracted.get("actions", []))
        weapon_phrase = self._build_weapon_phrase(extracted)
        if weapon_phrase and "ขู่" in actions_list:
            actions_list = [a for a in actions_list if a != "ขู่"]
        actions = self._combine_actions(actions_list)
        injuries = " ".join(sorted(set(extracted.get("injuries", []))))
        motives = " ".join(self._extract_motives(original))
        prov = self._locations_from_provinces(tokens)
        regex_locs = self._extract_locations_regex(original)
        locations = self._merge_locations(prov, regex_locs)
        compressed = self.compress_text(original)
        fallback = ""
        if not motives and not locations:
            fallback = " ".join(compressed.split()[:12])
        parts: List[str] = []
        if actions:
            parts.append(f"[\u0e01\u0e32\u0e23\u0e01\u0e23\u0e30\u0e17\u0e33] {actions}")
        if weapon_phrase:
            parts.append(f"[\u0e2d\u0e32\u0e27\u0e38\u0e18] {weapon_phrase}")
        if locations:
            parts.append(f"[\u0e2a\u0e16\u0e32\u0e19\u0e17\u0e35\u0e48] {locations}")
        if motives:
            parts.append(
                f"[\u0e1b\u0e23\u0e30\u0e40\u0e14\u0e47\u0e19/\u0e41\u0e23\u0e07\u0e08\u0e39\u0e07\u0e43\u0e08] {motives}"
            )
        elif fallback:
            parts.append(f"[\u0e1a\u0e23\u0e34\u0e1a\u0e17] {fallback}")
        if injuries:
            parts.append(f"[\u0e01\u0e32\u0e23\u0e1a\u0e32\u0e14\u0e40\u0e08\u0e47\u0e1a] {injuries}")
        return " ".join(parts).strip()

    def build_embedding_text(self, case: CaseData) -> str:
        original_text = self.clean_text(case.fact_summary)
        sections: List[str] = []
        if original_text:
            tokens = word_tokenize(original_text, engine=self._token_engine)
            extracted = self._extract_keywords_from_tokens(tokens)
            summarized = self._summarize_fact_core(original_text, tokens, extracted)
            normalized = self.normalize(extracted)
        else:
            summarized = ""
            normalized = []

        pf = self._pfx
        if summarized:
            sections.append(f"[{pf['fact']}] {summarized}")
        if (case.casetype or "").strip():
            sections.append(f"[{pf['casetype']}] {(case.casetype or '').strip()}")
        if (case.legal_basis or "").strip():
            sections.append(f"[{pf['legal']}] {(case.legal_basis or '').strip()}")
        if (case.prosecutor_opinion or "").strip():
            sections.append(f"[{pf['prosecutor']}] {(case.prosecutor_opinion or '').strip()}")
        tags = " ".join(normalized)
        if tags:
            sections.append(f"[{pf['tags']}] {tags}")
        return " ".join(sections).strip()

    def preprocess_query_for_search(self, query: str) -> str:
        cleaned = self.clean_text(query)
        if not cleaned:
            return ""
        tokens = word_tokenize(cleaned, engine=self._token_engine)
        extracted = self._extract_keywords_from_tokens(tokens)
        summarized = self._summarize_fact_core(cleaned, tokens, extracted)
        pf = self._pfx
        if summarized:
            return f"[{pf['query']}] {summarized}"
        compressed = self.compress_text(cleaned) or cleaned
        return f"[{pf['query_fallback']}] {compressed}"
