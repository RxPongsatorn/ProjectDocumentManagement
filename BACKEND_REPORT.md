# Backend Report (DocumentManagement)

เอกสารนี้สรุปการทำงานของโค้ดฝั่ง backend โดยอ้างอิง “ช่วงบรรทัด” ของแต่ละไฟล์ (ตามสถานะโค้ดใน workspace ณ ตอนจัดทำรายงาน)

## ภาพรวมสถาปัตยกรรม

- **Framework**: FastAPI
- **Auth**: session cookie (`session_id`) เก็บในตาราง `sessions`
- **DB**: PostgreSQL + pgvector (`LegalCase.embedding` เป็น Vector(768))
- **เอกสาร**: สร้างไฟล์ `.docx` (ต้นฉบับ) + `.docx/.pdf` (blind/redacted)
- **สิทธิ์**:
  - `admin`: สร้าง/แก้/ลบเอกสารได้ (เฉพาะของตัวเอง), เห็น unblinded เฉพาะเอกสารที่ตัวเองสร้าง
  - `user`: เห็น/ดาวน์โหลดได้เฉพาะเอกสารที่ **มีไฟล์ blind แล้ว** เท่านั้น
- **Search**: embed query → ค้นด้วย pgvector → กรอง similarity > 0.6

---

## `main.py`

- **บรรทัด 1–12**: import FastAPI, routers (`search`, `user_management`, `documents`, `dashboard`), CORS middleware, DB engine/Base/session และฟังก์ชัน hash password
- **บรรทัด 13–18**: สร้าง `app`, สั่ง `Base.metadata.create_all()` และ `ensure_schema()` เพื่อสร้าง/อัปเกรด schema ที่จำเป็น (add column if not exists)
- **บรรทัด 19–45**: `ensure_bootstrap_admin()`  
  - เช็คว่ามี user `role=admin` แล้วหรือยัง  
  - ถ้าไม่มี: ถ้ามี `username=admin` อยู่แล้วจะอัปเกรด role เป็น admin; ถ้าไม่มีก็สร้างใหม่ `admin/admin01`
- **บรรทัด 46–51**: include routers เข้ากับ FastAPI
- **บรรทัด 53–59**: เปิด CORS (`allow_origins=["*"]`, `allow_credentials=True`) เพื่อให้ frontend ส่ง cookie ได้

---

## `app/db.py`

- **บรรทัด 1–11**: สร้าง SQLAlchemy engine จาก `DATABASE_URL`, สร้าง `SessionLocal`, และ `Base`
- **บรรทัด 13–18**: generator `get_db()` สำหรับ dependency injection (เปิด/ปิด session)
- **บรรทัด 21–38**: `ensure_schema()` ใช้ `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` เพื่อเพิ่มคอลัมน์ที่ create_all เพิ่มไม่ได้ เช่น  
  - `users.role`  
  - `legal_cases.redacted_doc_path`, `redacted_pdf_path`, `created_by_user_id`, `embedding_source_text`

---

## `app/models.py`

### `LegalCase`
- **บรรทัด 1–6**: import SQLAlchemy/pgvector
- **บรรทัด 7–27**: นิยามตาราง `legal_cases`
  - `embedding: Vector(768)` เวกเตอร์สำหรับ search
  - `embedding_source_text: Text` ข้อความสรุปที่ใช้ทำเวกเตอร์ (เก็บไว้เพื่อ debug/แสดงผล)
  - `doc_path`: path ไฟล์เต็ม (unblinded)
  - `redacted_doc_path`, `redacted_pdf_path`: path ไฟล์ blind/redacted
  - `created_by_user_id`: FK → `users.id` (ผู้สร้างเอกสาร)
  - `created_at`: เวลาสร้าง

### `User` และ `Session`
- **บรรทัด 38–50**: `users`
  - `role`: `"admin"` หรือ `"user"`
  - `is_active`: เปิด/ปิดการใช้งาน
- **บรรทัด 52–62**: `sessions`
  - เก็บ session cookie (`session_id`) + expiry

---

## `app/auth.py`

- **บรรทัด 1–8**: ตั้งค่า passlib `CryptContext` (pbkdf2_sha256)
- **บรรทัด 10–14**: `hash_password()` / `verify_password()`
- **บรรทัด 16–20**: สร้าง session id แบบสุ่ม + กำหนดวันหมดอายุ session (default 7 วัน)

---

## `app/deps.py`

- **บรรทัด 1–7**: import dependency
- **บรรทัด 9–48**: `get_current_user()`  
  - อ่าน cookie `session_id`  
  - query `Session` ใน DB  
  - ตรวจ expiry → ถ้าหมดอายุลบ session แล้วตอบ 401  
  - ตรวจ `user.is_active` → ถ้า false ตอบ 403  
  - คืน `User` object
- **บรรทัด 51–57**: `require_admin()` ตรวจ role ต้องเป็น admin ไม่งั้น 403

---

## `app/schemas.py`

- **บรรทัด 1–2**: import pydantic
- **บรรทัด 5–8**: `LoginRequest`
- **บรรทัด 10**: `Role` จำกัดค่า `"admin" | "user"`
- **บรรทัด 13–19**: `UserResponse`
- **บรรทัด 22–32**: request model สำหรับ admin สร้าง/แก้ user
- **บรรทัด 34–45**: `CaseRequest` คือ payload สำหรับสร้าง/แก้เอกสาร

---

## `app/build_redacted_data.py`

- **บรรทัด 4–27**: `build_redacted_data()`  
  - clone ข้อมูลคดี  
  - mask ชื่อ/เลขบัญชี/บัตรประชาชน/ทะเบียนรถ  
  - replace ค่าที่ mask แล้วใน `fact_summary` ด้วย
- **บรรทัด 29–49**: ฟังก์ชัน mask แต่ละชนิด (ให้ผลแบบ “blind”)

---

## `app/nlp_processor.py`

ไฟล์นี้แปลง “fact_summary + บริบทบางส่วน” → **ข้อความสรุป (clean) สำหรับทำ embedding**

- **บรรทัด 1–37**: `CaseData` + `from_extraction()` สำหรับ map dict จาก AI/JSON ให้เป็น object
- **บรรทัด 40–85**: `NLPProcessor.__init__()`  
  - กำหนดชุดคีย์เวิร์ด: violence/injury/weapon/drug/theft/fraud  
  - กำหนด stop-words เพื่อ “ตัดคำฟุ่มเฟือย”  
  - sort stop-words จากยาวไปสั้นเพื่อ replace ได้เสถียร
- **บรรทัด 86–96**: `clean_text()` + `compress_text()` (ลด whitespace และตัด stop-words)
- **บรรทัด 98–107**: `extract_keywords()` ดึง keyword ที่พบในข้อความ
- **บรรทัด 109–123**: `normalize()` สร้าง “ป้ายหมวด” เช่น `คดีทำร้ายร่างกาย`, `ใช้อาวุธ`, `คดีฉ้อโกง`
- **บรรทัด 125–135**: `_combine_actions()` รวมคำกระทำให้สั้น (เช่น ชก+ต่อย → ชกต่อย)
- **บรรทัด 137–165**: `_extract_motives()` ดึง “ประเด็น/เหตุ” เช่น `เรื่องที่จอดรถ` หรือวลีหลัง `โต้เถียง/ทะเลาะ/มีปากเสียง`
- **บรรทัด 167–181**: `_extract_locations()` ดึงสถานที่สั้น ๆ รูปแบบ `ใน...`
- **บรรทัด 183–193**: `_build_weapon_phrase()` สร้างวลีอาวุธ เช่น `ใช้อาวุธมีดขู่`
- **บรรทัด 195–232**: `summarize_fact_for_embedding()`  
  - รวมเฉพาะ keyword สำคัญ: actions + weapon phrase + location + motives + injuries  
  - ถ้าไม่มี motives/location จะ fallback ด้วย compressed text สั้น ๆ
- **บรรทัด 234–251**: `build_embedding_text()` สร้าง final text สำหรับ embed:  
  `summarized_fact + casetype + legal_basis + normalized_labels`
- **บรรทัด 253–257**: `preprocess_query_for_search()` ทำให้ query มีรูปแบบใกล้กับข้อความตอน ingest

---

## `app/embedded_text.py`

- **บรรทัด 1–9**: โหลด SentenceTransformer (`intfloat/multilingual-e5-base`) และสร้าง NLPProcessor
- **บรรทัด 12–16**: `build_search_text(d)` → เรียก `NLPProcessor.build_embedding_text()` เพื่อได้ “ข้อความสรุป”
- **บรรทัด 19–23**: `embed_text(text)` → encode เป็น vector โดย prefix `passage:`
- **บรรทัด 26–32**: `embed_query(text)` → preprocess query แล้ว encode ด้วย prefix `query:`

---

## `app/case_pipeline.py`

- **บรรทัด 1–6**: import service ต่าง ๆ (AI, embedding, doc generation, redaction, model)

### `process_case_text(raw_text, db, created_by_user_id, existing_row)`
- **บรรทัด 8–17**: เรียก `classify_text()` ให้ AI สกัดข้อมูลเป็น dict → แปลงเป็น search text → embed เป็น vector
- **บรรทัด 18–22**: สร้างเอกสารเต็ม + สร้าง redacted + แปลงเป็น PDF
- **บรรทัด 24–46**: insert/update `LegalCase` พร้อม `embedding_source_text`, `created_by_user_id`
- **บรรทัด 48–57**: คืนผลลัพธ์ (รวม `embedding_source_text` เพื่อ debug)

### `process_case_dict(case_data, db, created_by_user_id, existing_row)`
- **บรรทัด 60–68**: สร้าง `redacted_data` ก่อน → ใช้ redacted ทำ search text + embedding (เพื่อให้เวกเตอร์ไม่รวม PII)
- **บรรทัด 70–72**: สร้างไฟล์เอกสารเต็ม + blind doc + blind pdf
- **บรรทัด 74–97**: insert/update `LegalCase`
- **บรรทัด 98–107**: คืนผลลัพธ์

### `build_raw_text_from_json(case_data)`
- **บรรทัด 110–122**: ประกอบข้อความจากฟิลด์ต่าง ๆ (ใช้กรณีต้องการป้อน raw text ให้ AI)

---

## `app/generate_doc.py`

- **บรรทัด 1–7**: กำหนด template path และ output dir
- **บรรทัด 9–12**: `generate_doc()` wrapper
- **บรรทัด 14–31**: `get_next_file_number()` หาเลขลำดับไฟล์ `case_{n}.docx`
- **บรรทัด 34–57**: `create_word()`  
  - render template ด้วย context (victim/suspect/date/fact/law/opinion)  
  - save เป็นไฟล์ docx ใหม่

---

## `app/generate_pdf.py`

- **บรรทัด 1–3**: import subprocess/os
- **บรรทัด 4–16**: `convert_docx_to_pdf()` เรียก `libreoffice --headless --convert-to pdf`

---

## `app/pdf_service.py`

- **บรรทัด 1–2**: import pdfplumber และ pythainlp normalize
- **บรรทัด 4–13**: `extract_text_from_pdf()` อ่านข้อความจากทุกหน้าแล้วรวมเป็น string
- **บรรทัด 16–20**: `normalize_thai_text()` normalize ภาษาไทย + trim whitespace

---

## `app/ai_service.py`

- **บรรทัด 1–8**: ตั้งค่า `OLLAMA_HOST` และสร้าง client
- **บรรทัด 9–21**: `empty_case_data()` โครงสร้างผลลัพธ์ default
- **บรรทัด 24–50**: `classify_text()` สร้าง prompt บังคับให้ตอบ JSON fields ที่ต้องการ
- **บรรทัด 52–56**: เรียก `client.chat()` เพื่อได้คำตอบ
- **บรรทัด 57–85**: ทำความสะอาดผลลัพธ์ (ตัด code fence) แล้ว parse JSON; ถ้า parse ไม่ได้จะพยายามดึง `{...}`; สุดท้าย fallback เป็น empty_case_data

---

## `app/document_access.py`

- **บรรทัด 1–8**: อธิบาย policy และ import models
- **บรรทัด 10–15**: `is_admin()` / `can_view_unblinded()` (admin + เป็นผู้สร้าง)
- **บรรทัด 18–28**: `has_public_blinded_copy()` และ `user_may_access_document()`  
  - ถ้าเห็น unblinded ได้ → เข้าถึงได้  
  - ไม่งั้นต้องมี blind copy ถึงเข้าถึงได้
- **บรรทัด 31–34**: `resolve_doc_path_for_user()` คืน path ที่ user ควรเห็น (unblinded หรือ blind)
- **บรรทัด 37–59**: `serialize_case()` สร้าง JSON response กลางที่ใช้ใน documents/search

---

## `api/user_management.py`

- **บรรทัด 1–20**: import FastAPI/SQLAlchemy + auth helpers + schemas
- **บรรทัด 21**: กำหนด router prefix `/user_management`

### Session endpoints
- **บรรทัด 24–62**: `POST /user_management/login`  
  - ตรวจ username/password + is_active  
  - สร้าง session row และ set cookie `session_id`
- **บรรทัด 64–77**: `POST /user_management/logout`  
  - ลบ session จาก DB และล้าง cookie
- **บรรทัด 80–86**: `GET /user_management/me` คืนข้อมูลผู้ใช้ปัจจุบัน

### Admin user CRUD
- **บรรทัด 89–104**: `GET /user_management/users` (admin เท่านั้น) list ผู้ใช้ทั้งหมด
- **บรรทัด 107–135**: `POST /user_management/admin/users` (admin) สร้างผู้ใช้ใหม่ (กำหนด role/is_active ได้)
- **บรรทัด 137–192**: `PATCH /user_management/admin/users/{id}` (admin) แก้ role/is_active  
  - กันกรณี “ลดสิทธิ์ admin คนสุดท้าย”  
  - กันกรณี “ปิดใช้งาน admin active คนสุดท้าย”
- **บรรทัด 194–225**: `DELETE /user_management/admin/users/{id}` (admin) ลบ user  
  - ห้ามลบตัวเอง  
  - ห้ามลบ admin คนสุดท้าย

---

## `api/documents.py`

- **บรรทัด 1–20**: import router/deps/models + helpers จาก `document_access`
- **บรรทัด 20**: router prefix `/documents`
- **บรรทัด 23–30**: `POST /documents` (admin) สร้างเอกสารผ่าน `process_case_dict`
- **บรรทัด 33–48**: `GET /documents`  
  - user: filter เฉพาะคดีที่มี `redacted_doc_path`  
  - admin: เห็นทั้งหมด  
  - serialize ด้วย `serialize_case()`
- **บรรทัด 51–60**: `GET /documents/{id}` ต้องผ่าน `user_may_access_document`
- **บรรทัด 63–98**: `GET /documents/{id}/download`  
  - `version=unblinded` เฉพาะ creator admin  
  - `version=blind` ต้องมีไฟล์ blind  
  - `auto` เลือกตามสิทธิ์
- **บรรทัด 101–117**: `PUT /documents/{id}` (admin) แก้/regen ได้เฉพาะเอกสารที่สร้างเอง
- **บรรทัด 120–143**: `DELETE /documents/{id}` (admin) ลบได้เฉพาะของตัวเอง และลบไฟล์บนดิสก์แบบ best-effort

---

## `api/search.py`

- **บรรทัด 1–15**: ตั้งค่าคงที่ของ search (threshold/limits) และ helper cosine similarity
- **บรรทัด 18–24**: `_cosine_similarity()` คำนวณ cosine similarity
- **บรรทัด 27–93**: `POST /search/`  
  - embed query ด้วย `embed_query()`  
  - ดึง candidates จาก pgvector (`cosine_distance`)  
  - user: จำกัด candidates เฉพาะที่มี blind  
  - กรองผล `similarity > 0.6`  
  - enforce สิทธิ์: ถ้าไม่ใช่ creator admin ต้องมี blind  
  - คืนผลสูงสุด 10 รายการ + ข้อความ “ไม่พบ” เมื่อไม่มีผล

---

## `api/dashboard.py`

- **บรรทัด 1–13**: router `/admin` (admin เท่านั้น)
- **บรรทัด 16–74**: `GET /admin/dashboard`  
  - นับจำนวน user (รวม/active/admin/regular)  
  - นับจำนวนเอกสารทั้งหมด + จำนวนที่มี blind file  
  - สรุปจำนวนเอกสารตาม `casetype` (ค่าว่าง/None → `ไม่ระบุ`)

---

## `api/vector_test.py` (เก็บไว้เป็นไฟล์ตัวอย่าง)

ไฟล์นี้เป็น “ตัวอย่างทดลอง” FAISS + MiniLM และ rule-based NLP แบบ verbose (พิมพ์ log) เพื่อสาธิตแนวคิดการบีบข้อความก่อน embed  
> **ระบบจริง** ใช้ `app/nlp_processor.py` + `app/embedded_text.py` + pgvector แทน

