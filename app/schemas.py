from typing import Literal, Optional
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str


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


class DocumentUpdateRequest(BaseModel):
    # for regenerate content; optional for partial update
    victim_name: Optional[str] = None
    suspect_name: Optional[str] = None
    event_date: Optional[str] = None
    fact_summary: Optional[str] = None
    legal_basis: Optional[str] = None
    prosecutor_opinion: Optional[str] = None
    casetype: Optional[str] = None
    bank_account: Optional[str] = None
    id_card: Optional[str] = None
    plate_number: Optional[str] = None