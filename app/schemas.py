from typing import Literal, Optional

from pydantic import BaseModel, Field
class LoginRequest(BaseModel):
    username: str
    password: str
Role = Literal["admin", "user"]
class UserResponse(BaseModel):
    id: int
    username: str
    role: str = "user"
    class Config:
        from_attributes = True
class AdminCreateUserRequest(BaseModel):
    username: str
    password: str
    role: Role = "user"
    is_active: bool = True
class AdminUpdateUserRequest(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None
class CaseRequest(BaseModel):
    victim_name: str
    suspect_name: str
    event_date: str
    fact_summary: str
    legal_basis: str
    prosecutor_opinion: str
    filename: str | None = None
    casetype: str | None = None
    bank_account: str | None = None
    id_card: str | None = None
    plate_number: str | None = None


class BulkCaseImportRequest(BaseModel):
    """Multiple cases per request; use JSON key items as a list of cases."""

    items: list[CaseRequest] = Field(..., min_length=1)
