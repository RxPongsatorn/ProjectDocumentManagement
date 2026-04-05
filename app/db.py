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
    """
    Make local/dev upgrades resilient when the DB already exists.
    create_all() won't add new columns to existing tables.
    """
    stmts: list[str] = [
        # user roles
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
        # redacted + ownership for documents
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS redacted_doc_path TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS redacted_pdf_path TEXT",
        "ALTER TABLE legal_cases ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
    ]

    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))