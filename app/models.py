from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db import Base

class LegalCase(Base):
    __tablename__ = "legal_cases"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String, index=True)
    casetype = Column(String)

    event_date = Column(String)
    embedding = Column(Vector(768))
    # original/unblinded document path
    doc_path = Column(Text)
    # blinded/redacted variants (safe to show to all authenticated users)
    redacted_doc_path = Column(Text, nullable=True)
    redacted_pdf_path = Column(Text, nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user = relationship("User", back_populates="created_cases")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # victim_name = Column(String)
    # suspect_name = Column(String)
    # fact_summary = Column(Text)
    # legal_basis = Column(Text)
    # prosecutor_opinion = Column(Text)
    # search_text = Column(Text)

  

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=True, server_default="user")  # "admin" | "user"
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    created_cases = relationship("LegalCase", back_populates="created_by_user")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")