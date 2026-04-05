"""กติกามองเห็นเอกสาร: เผยแพร่ blind แล้ว = ทุกคนเห็นได้; ฉบับร่าง = ผู้สร้างเห็นของตัวเอง (ทุก role); ฉบับเต็มก่อนเผยแพร่ = เฉพาะผู้สร้าง."""
from __future__ import annotations

from app.models import LegalCase, User


def user_role(user: User) -> str:
    return (getattr(user, "role", None) or "user").strip() or "user"


def is_creator(user: User, row: LegalCase) -> bool:
    return row.created_by_user_id is not None and row.created_by_user_id == user.id


def is_blind_published(row: LegalCase) -> bool:
    return bool(getattr(row, "blind_published", False))


def can_list_document(user: User, row: LegalCase) -> bool:
    """เผยแพร่แล้วทุกคนเห็นได้; ยังไม่เผยแพร่ = เห็นเฉพาะผู้สร้าง (ให้สอดคล้องกับฟอร์มสร้างเอกสารจาก frontend)."""
    if is_blind_published(row):
        return True
    return is_creator(user, row)


def can_vector_search_document(user: User, row: LegalCase) -> bool:
    """ใช้ชุดเดียวกับ list — ค้นหาได้เฉพาะเอกสารที่ผู้ใช้มีสิทธิ์รู้จัก."""
    return can_list_document(user, row)


def can_view_unblinded(user: User, row: LegalCase) -> bool:
    """ฉบับเต็ม: เฉพาะผู้สร้าง (ดาวน์โหลด/ดูก่อนเผยแพร่)."""
    return is_creator(user, row)


def can_publish_document(user: User, row: LegalCase) -> bool:
    return user_role(user) == "admin" and is_creator(user, row)


def can_mutate_document(user: User, row: LegalCase) -> bool:
    """แก้ไข/ลบ: เฉพาะผู้สร้าง (ไม่บังคับว่าเป็น admin)."""
    return is_creator(user, row)


def doc_path_for_api(user: User, row: LegalCase) -> str | None:
    """path ที่ส่งให้ client ดาวน์โหลด/แสดง (auto: เต็มถ้าเป็นผู้สร้าง ไม่งั้น blind)."""
    if can_view_unblinded(user, row):
        return row.doc_path
    return row.redacted_doc_path


def can_download_blind(user: User, row: LegalCase) -> bool:
    if is_blind_published(row):
        return True
    return can_view_unblinded(user, row)


def can_download_unblind(user: User, row: LegalCase) -> bool:
    return can_view_unblinded(user, row)
