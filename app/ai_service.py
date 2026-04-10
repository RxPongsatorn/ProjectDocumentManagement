import ollama
import os
import re
import json
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
client = ollama.Client(host=OLLAMA_HOST)
def empty_case_data() -> dict:
    return {
        "case_type": "",
        "victim_name": "",
        "suspect_name": "",
        "event_date": "",
        "fact_summary": "",
        "legal_basis": "",
        "prosecutor_opinion": "",
        "bank_account": "",
        "id_card": "",
        "plate_number": ""
    }
def classify_text(text: str) -> dict:
    prompt = f"""
    คุณคือระบบสกัดข้อมูลคดีภาษาไทย
    จงอ่านข้อความต่อไปนี้ แล้วตอบเป็น JSON เท่านั้น

    ต้องการ fields:
    - case_type
    - victim_name
    - suspect_name
    - event_date
    - fact_summary
    - legal_basis
    - prosecutor_opinion
    - bank_account
    - id_card
    - plate_number

    กติกา:
    - ถ้าไม่พบ ให้ใส่ ""
    - ห้ามอธิบายเพิ่ม
    - ห้ามใส่ markdown
    - ห้ามใส่ ```json
    - ตอบเป็น JSON object เท่านั้น

    ข้อความ:
    {text}
    """
    response = client.chat(
        model="deepseek-v3.1:671b-cloud",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response["message"]["content"]
    print("DEBUG AI RAW:", repr(content))
    if not content or not content.strip():
        return empty_case_data()
    content = content.strip()
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    print("DEBUG AI PARSE FAILED:", repr(content))
    return empty_case_data()