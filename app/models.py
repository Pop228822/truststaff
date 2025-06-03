from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, date
from typing import List

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_approved: bool = Field(default=False)
    company_name: Optional[str] = None
    city: Optional[str] = None
    inn_or_ogrn: Optional[str] = None
    passport_filename: Optional[str] = None
    verification_status: str = Field(default="not_requested")  # может быть not_requested / pending / approved / rejected
    rejection_reason: Optional[str] = None
    role: str = Field(default="user")
    is_email_verified: bool = Field(default=False)
    email_verification_token: Optional[str] = None
    password_reset_requested_at: Optional[datetime] = None
    is_blocked = Field(default=False)


class Employee(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    birth_date: date
    contact: Optional[str] = None
    created_by_user_id: int = Field(foreign_key="user.id")
    records: List["ReputationRecord"] = Relationship(back_populates="employee")


class ReputationRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(foreign_key="employee.id")
    employer_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    position: str
    hired_at: datetime
    fired_at: Optional[datetime] = None

    misconduct: Optional[str] = None
    dismissal_reason: Optional[str] = None
    commendation: Optional[str] = None

    employee: Optional[Employee] = Relationship(back_populates="records")


class LoginAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    ip_address: str
    success: bool
    attempt_time: datetime = Field(default_factory=datetime.utcnow)


class PendingUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    email_verification_token: str  # Храним токен подтверждения


class CheckLog(SQLModel, table=True):
    __tablename__ = "check_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RateLimit(SQLModel, table=True):
    __tablename__ = "rate_limit"
    ip_address: str = Field(primary_key=True)
    request_count: int
    window_start: datetime
