import os
import re
from datetime import datetime
from docxtpl import DocxTemplate
_THAI_MONTHS = (
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
def format_event_date_thai(raw: str) -> str:
    if raw is None or str(raw).strip() in ("", "-"):
        return "-" if not raw or str(raw).strip() == "" else str(raw).strip()
    s = str(raw).strip()
    m = _ISO_DATE.search(s)
    if not m:
        return s
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        datetime(y, mo, d)
    except ValueError:
        return s
    be = y + 543
    month_name = _THAI_MONTHS[mo - 1]
    thai = f"วันที่{d}เดือน{month_name}พ.ศ.{be}"
    before = s[: m.start()].rstrip()
    after = s[m.end() :].lstrip()
    parts = [p for p in (before, thai, after) if p]
    return " ".join(parts)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = "/app/app/templates/template.docx"
OUTPUT_DIR = "/app/app/documents"
def generate_doc(data: dict):
    file_path = create_word(data)
    return file_path
def get_next_file_number(output_dir: str) -> int:
    os.makedirs(output_dir, exist_ok=True)
    files = os.listdir(output_dir)
    numbers = []
    for f in files:
        if f.startswith("case_") and f.endswith(".docx"):
            try:
                num = int(f.replace("case_", "").replace(".docx", ""))
                numbers.append(num)
            except:
                pass
    if not numbers:
        return 1
    return max(numbers) + 1
def create_word(case_data: dict) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    doc = DocxTemplate(TEMPLATE_PATH)
    event_raw = case_data.get("event_date") or "-"
    event_display = (
        format_event_date_thai(event_raw) if event_raw not in (None, "", "-") else "-"
    )
    context = {
        "victim_name": case_data.get("victim_name", "-"),
        "suspect_name": case_data.get("suspect_name", "-"),
        "event_date": event_display,
        "fact_summary": case_data.get("fact_summary", "-"),
        "legal_basis": case_data.get("legal_basis", "-"),
        "prosecutor_opinion": case_data.get("prosecutor_opinion", "-"),
    }
    doc.render(context)
    next_number = get_next_file_number(OUTPUT_DIR)
    output_path = os.path.join(OUTPUT_DIR, f"case_{next_number}.docx")
    doc.save(output_path)
    return output_path