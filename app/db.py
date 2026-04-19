import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@db:5432/app_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def ensure_schema() -> None:
    stmts: list[str] = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS redacted_doc_path TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS embedding_source_text TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS fact_summary_blinded TEXT",
        "ALTER TABLE legal_cases ALTER COLUMN doc_path DROP NOT NULL",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS victim_name TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS suspect_name TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS fact_summary TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS legal_basis TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS prosecutor_opinion TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS bank_account TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS id_card TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS plate_number TEXT",
        """
        DO $migrate$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'legal_cases'
              AND column_name = 'case_data'
          ) THEN
            UPDATE legal_cases SET
              filename = COALESCE(filename, case_data->>'filename'),
              casetype = COALESCE(NULLIF(TRIM(casetype), ''), case_data->>'casetype', case_data->>'case_type'),
              event_date = COALESCE(NULLIF(TRIM(event_date), ''), case_data->>'event_date'),
              victim_name = COALESCE(NULLIF(TRIM(victim_name), ''), case_data->>'victim_name'),
              suspect_name = COALESCE(NULLIF(TRIM(suspect_name), ''), case_data->>'suspect_name'),
              fact_summary = COALESCE(NULLIF(TRIM(fact_summary), ''), case_data->>'fact_summary'),
              legal_basis = COALESCE(NULLIF(TRIM(legal_basis), ''), case_data->>'legal_basis'),
              prosecutor_opinion = COALESCE(NULLIF(TRIM(prosecutor_opinion), ''), case_data->>'prosecutor_opinion'),
              bank_account = COALESCE(NULLIF(TRIM(bank_account), ''), case_data->>'bank_account'),
              id_card = COALESCE(NULLIF(TRIM(id_card), ''), case_data->>'id_card'),
              plate_number = COALESCE(NULLIF(TRIM(plate_number), ''), case_data->>'plate_number')
            WHERE case_data IS NOT NULL;
          END IF;
        END
        $migrate$;
        """,
        "ALTER TABLE legal_cases DROP COLUMN IF EXISTS case_data",
        "ALTER TABLE legal_cases DROP COLUMN IF EXISTS redacted_pdf_path",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))