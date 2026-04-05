


def build_redacted_data(data: dict) -> dict:
    redacted = data.copy()

    redacted["victim_name"] = mask_name(data.get("victim_name", ""))
    redacted["suspect_name"] = mask_name(data.get("suspect_name", ""))
    redacted["bank_account"] = mask_bank_account(data.get("bank_account", ""))
    redacted["id_card"] = mask_id_card(data.get("id_card", ""))
    redacted["plate_number"] = mask_plate_number(data.get("plate_number", ""))

    # ถ้ามีข้อความยาว ต้องแทนใน fact_summary ด้วย
    fact = data.get("fact_summary", "")
    if data.get("victim_name"):
        fact = fact.replace(data["victim_name"], redacted["victim_name"])
    if data.get("suspect_name"):
        fact = fact.replace(data["suspect_name"], redacted["suspect_name"])
    if data.get("bank_account"):
        fact = fact.replace(data["bank_account"], redacted["bank_account"])
    if data.get("id_card"):
        fact = fact.replace(data["id_card"], redacted["id_card"])
    if data.get("plate_number"):
        fact = fact.replace(data["plate_number"], redacted["plate_number"])

    redacted["fact_summary"] = fact
    return redacted

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