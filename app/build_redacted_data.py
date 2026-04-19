"""สร้างสำเนาข้อมูลคดีที่ปกปิดข้อมูลระบุตัวตน (ชื่อ บัญชี เลขบัตร ทะเบียน) สำหรับเอกสารสาธารณะ / embedding."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# คำนำหน้าชื่อที่มักตัดออกเมื่อเปรียบกับชื่อในสรุปข้อเท็จจริง
_NAME_PREFIX = re.compile(
    r"^(นาย|นาง|นางสาว|เด็กชาย|เด็กหญิง|ด\.ช\.|ด\.ญ\.|Mr\.?|Mrs\.?|Ms\.?)\s*",
    re.IGNORECASE,
)


def mask_name(name: str) -> str:
    if not name:
        return ""
    return "XXX"


def mask_bank_account(acc: str) -> str:
    if not acc:
        return ""
    return "XXX-XX-XXXX-X"


def mask_id_card(id_card: str) -> str:
    if not id_card:
        return ""
    if len(id_card) >= 4:
        return id_card[:4] + "X" * (len(id_card) - 4)
    return "X" * len(id_card)


def mask_plate_number(plate: str) -> str:
    if not plate:
        return ""
    return "XXXX"


def _digits_only(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _name_variants(raw: str) -> List[str]:
    """สร้างชุดคำที่อาจปรากฏในเนื้อความ (มี/ไม่มีคำนำหน้า แยกชื่อ-นามสกุล)."""
    s = (raw or "").strip()
    if len(s) < 2:
        return []
    seen: set[str] = set()
    out: List[str] = []

    def add(x: str) -> None:
        t = x.strip()
        if len(t) < 2 or t in seen:
            return
        seen.add(t)
        out.append(t)

    add(s)
    stripped = _NAME_PREFIX.sub("", s).strip()
    if stripped:
        add(stripped)
    parts = stripped.split()
    if len(parts) >= 2:
        add(parts[0])
        add(parts[-1])
        add(f"{parts[0]} {parts[-1]}")
    if len(parts) >= 3:
        add(" ".join(parts[:2]))
        add(" ".join(parts[-2:]))
    return out


def _id_card_format_variants(d13: str) -> List[str]:
    """รูปแบบเลขบัตร 13 หลักที่พบบ่อยในเอกสาร (มี/ไม่มีขีด/ช่องว่าง)."""
    if len(d13) != 13 or not d13.isdigit():
        return []
    d = d13
    variants = [
        d,
        f"{d[0]}-{d[1:5]}-{d[5:10]}-{d[10:12]}-{d[12]}",
        f"{d[0]} {d[1:5]} {d[5:10]} {d[10:12]} {d[12]}",
        f"{d[0]}-{d[1:5]}-{d[5:10]}-{d[10:12]} {d[12]}",
    ]
    # บางแหล่งพิมพ์ติดกันหรือมีช่องไม่สม่ำเสมอ
    seen: set[str] = set()
    uniq: List[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def _bank_variants(raw: str) -> List[str]:
    s = (raw or "").strip()
    if not s:
        return []
    d = _digits_only(s)
    out: List[str] = [s]
    if d and d != s:
        out.append(d)
    return out


def _plate_variants(raw: str) -> List[str]:
    s = (raw or "").strip()
    if not s:
        return []
    return [s, s.replace(" ", ""), s.upper(), s.lower()]


def _build_replacement_map(data: dict, redacted_fields: dict) -> Dict[str, str]:
    """รวมทุกสตริงที่ต้องแทนที่ → ค่าหลังปกปิด (คีย์ยาวก่อนเมื่อ sort)."""
    pairs: Dict[str, str] = {}

    def add_many(variants: List[str], replacement: str) -> None:
        for v in variants:
            v = v.strip() if v else v
            if not v or len(v) < 1:
                continue
            if v not in pairs:
                pairs[v] = replacement

    # ชื่อผู้เสียหาย / ผู้ต้องหา — หลายรูปแบบในย่อหน้า
    for key in ("victim_name", "suspect_name"):
        raw = data.get(key) or ""
        repl = redacted_fields.get(key) or ""
        add_many(_name_variants(str(raw)), repl)

    for key in ("bank_account",):
        raw = data.get(key) or ""
        repl = redacted_fields.get(key) or ""
        add_many(_bank_variants(str(raw)), repl)

    id_raw = str(data.get("id_card") or "")
    id_repl = redacted_fields.get("id_card") or ""
    d13 = _digits_only(id_raw)
    if len(d13) == 13:
        add_many(_id_card_format_variants(d13), id_repl)
    elif id_raw.strip():
        add_many([id_raw.strip(), id_raw], id_repl)

    plate_raw = data.get("plate_number") or ""
    plate_repl = redacted_fields.get("plate_number") or ""
    for v in _plate_variants(str(plate_raw)):
        if v and v not in pairs:
            pairs[v] = plate_repl

    return pairs


def _sorted_pairs(pairs: Dict[str, str]) -> List[Tuple[str, str]]:
    return sorted(pairs.items(), key=lambda x: -len(x[0]))


def _redact_narrative(text: str, pairs: List[Tuple[str, str]]) -> str:
    if not text:
        return ""
    out = text
    for orig, repl in pairs:
        if orig and orig in out:
            out = out.replace(orig, repl)
    return out


def _replace_flexible_id_card(text: str, id_digits: str, masked_display: str) -> str:
    """
    แทนที่เลขบัตร 13 หลักในเนื้อความ แม้มีช่องว่าง/ขีด/จุดคั่นระหว่างตัวเลขไม่เหมือนในฟิลด์
    """
    if len(id_digits) != 13 or not id_digits.isdigit():
        return text
    if id_digits in text:
        text = text.replace(id_digits, masked_display)
    # อนุญาตตัวคั่นระหว่างตัวเลขแต่ละหลัก (เช่น 1 - 2345 - 67890 - 12 - 3)
    sep = r"[\s\-._]*"
    pattern = sep.join(re.escape(c) for c in id_digits)
    return re.sub(pattern, masked_display, text)


def build_redacted_data(data: dict) -> dict:
    """
    ปกปิดฟิลด์โครงสร้าง และแทนที่ข้อความอ่อนไหวในย่อหน้า
    (fact_summary / legal_basis / prosecutor_opinion)

    ใช้ทั้งการแมตช์ชื่อหลายแบบ (มี/ไม่มีคำนำหน้า, แยกชื่อ-สกุล)
    และรูปแบบเลขบัตรที่จัดรูปแบบต่างกัน
    """
    redacted = dict(data)
    redacted["victim_name"] = mask_name(data.get("victim_name", ""))
    redacted["suspect_name"] = mask_name(data.get("suspect_name", ""))
    redacted["bank_account"] = mask_bank_account(data.get("bank_account", ""))
    redacted["id_card"] = mask_id_card(data.get("id_card", ""))
    redacted["plate_number"] = mask_plate_number(data.get("plate_number", ""))

    pair_map = _build_replacement_map(data, redacted)
    ordered = _sorted_pairs(pair_map)
    id_masked = redacted["id_card"] or ""
    id_digits = _digits_only(str(data.get("id_card") or ""))

    def redact_block(t: str) -> str:
        s = _redact_narrative(str(t or ""), ordered)
        s = _replace_flexible_id_card(s, id_digits, id_masked)
        return s

    redacted["fact_summary"] = redact_block(data.get("fact_summary"))
    redacted["legal_basis"] = redact_block(data.get("legal_basis"))
    redacted["prosecutor_opinion"] = redact_block(data.get("prosecutor_opinion"))
    return redacted
