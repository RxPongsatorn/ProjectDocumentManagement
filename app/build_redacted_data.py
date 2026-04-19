"""สร้างสำเนาข้อมูลคดีที่ปกปิดข้อมูลระบุตัวตน (ชื่อ บัญชี เลขบัตร ทะเบียน) สำหรับเอกสารสาธารณะ / embedding."""


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


def _replacement_pairs(data: dict, redacted_fields: dict) -> list[tuple[str, str]]:
    """คู่ (ข้อความต้นฉบับ, ค่าที่แทนที่) เรียงจากยาวไปสั้น เพื่อลดปัญหา substring."""
    pairs: dict[str, str] = {}
    for key in ("victim_name", "suspect_name", "bank_account", "id_card", "plate_number"):
        raw = data.get(key) or ""
        if not str(raw).strip():
            continue
        repl = redacted_fields.get(key) or ""
        for variant in {str(raw), str(raw).strip()}:
            if variant and variant not in pairs:
                pairs[variant] = repl
    return sorted(pairs.items(), key=lambda x: -len(x[0]))


def _redact_narrative(text: str, pairs: list[tuple[str, str]]) -> str:
    if not text:
        return ""
    out = text
    for orig, repl in pairs:
        if orig and orig in out:
            out = out.replace(orig, repl)
    return out


def build_redacted_data(data: dict) -> dict:
    """
    ปกปิดฟิลด์โครงสร้าง และแทนที่ข้อความที่ตรงกับค่าในฟิลด์เหล่านั้น
    ภายใน fact_summary / legal_basis / prosecutor_opinion

    หมายเหตุ: ถ้าในย่อหน้าใช้ชื่อย่อ/คำที่ต่างจากค่าในฟิลด์เป๊ะ ๆ จะไม่ถูกแทนที่ — ต้องให้ตรงกับข้อมูลในฟิลด์
    """
    redacted = dict(data)
    redacted["victim_name"] = mask_name(data.get("victim_name", ""))
    redacted["suspect_name"] = mask_name(data.get("suspect_name", ""))
    redacted["bank_account"] = mask_bank_account(data.get("bank_account", ""))
    redacted["id_card"] = mask_id_card(data.get("id_card", ""))
    redacted["plate_number"] = mask_plate_number(data.get("plate_number", ""))

    pairs = _replacement_pairs(data, redacted)

    redacted["fact_summary"] = _redact_narrative(str(data.get("fact_summary") or ""), pairs)
    redacted["legal_basis"] = _redact_narrative(str(data.get("legal_basis") or ""), pairs)
    redacted["prosecutor_opinion"] = _redact_narrative(
        str(data.get("prosecutor_opinion") or ""), pairs
    )
    return redacted
