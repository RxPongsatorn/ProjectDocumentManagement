import os
from docxtpl import DocxTemplate

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

    context = {
        "victim_name": case_data.get("victim_name", "-"),
        "suspect_name": case_data.get("suspect_name", "-"),
        "event_date": case_data.get("event_date", "-"),
        "fact_summary": case_data.get("fact_summary", "-"),
        "legal_basis": case_data.get("legal_basis", "-"),
        "prosecutor_opinion": case_data.get("prosecutor_opinion", "-"),
    }

    doc.render(context)

    # หาเลขไฟล์ถัดไป
    next_number = get_next_file_number(OUTPUT_DIR)

    output_path = os.path.join(OUTPUT_DIR, f"case_{next_number}.docx")

    doc.save(output_path)

    return output_path