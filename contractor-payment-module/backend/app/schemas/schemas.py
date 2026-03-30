from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class SetupAdminRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = "Admin"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    role: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "manager"


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Contractors ───────────────────────────────────────────────────────────────

class ContractorCreate(BaseModel):
    name: str
    phone: str
    outlet: str
    hourly_rate: float


class ContractorUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    outlet: Optional[str] = None
    hourly_rate: Optional[float] = None
    status: Optional[str] = None


class ContractorRegisterConfirm(BaseModel):
    ic_number: str
    name: Optional[str] = None  # allow name correction


class ContractorOut(BaseModel):
    id: UUID
    name: str
    phone: str
    outlet: str
    hourly_rate: float
    status: str
    acquirer_id: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    ic_number: Optional[str] = None
    registration_token: UUID
    registered_at: Optional[datetime] = None
    qr_image_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContractorPublicOut(BaseModel):
    id: UUID
    name: str
    outlet: str
    hourly_rate: float
    status: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    registration_token: UUID


class QRParseResult(BaseModel):
    acquirer_id: str
    account_number: str
    bank_name: str
    payee_name: str
    is_duitnow: bool


# ── Timesheets ─────────────────────────────────────────────────────────────────

class TimesheetSubmit(BaseModel):
    year: int
    month: int
    outlet: Optional[str] = None  # overrides contractor's registered outlet for this submission
    week1_hours: float = 0
    week2_hours: float = 0
    week3_hours: float = 0
    week4_hours: float = 0

    def model_post_init(self, __context):
        for field in ("week1_hours", "week2_hours", "week3_hours", "week4_hours"):
            if getattr(self, field) < 0:
                raise ValueError(f"{field} must be non-negative")


class TimesheetUpdate(BaseModel):
    week1_hours: Optional[float] = None
    week2_hours: Optional[float] = None
    week3_hours: Optional[float] = None
    week4_hours: Optional[float] = None
    status: Optional[str] = None


class TimesheetReject(BaseModel):
    rejection_reason: str


class DayEntry(BaseModel):
    day: int
    hours: float
    outlet: Optional[str] = None


class TimesheetSubmitDays(BaseModel):
    year: int
    month: int
    outlet: Optional[str] = None
    days: list[DayEntry]


class DayEntryOut(BaseModel):
    id: UUID
    contractor_id: UUID
    year: int
    month: int
    day: int
    hours: float
    outlet: str
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DayCurrentStateOut(BaseModel):
    id: UUID
    day: int
    hours: float
    outlet: str
    status: str
    hourly_rate: Optional[float] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DayRateUpdate(BaseModel):
    hourly_rate: float


class DayLogOut(BaseModel):
    id: UUID
    contractor_id: UUID
    year: int
    month: int
    day: int
    event: str
    hours: Optional[float] = None
    outlet: Optional[str] = None
    rejection_reason: Optional[str] = None
    actor_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TimesheetOut(BaseModel):
    id: UUID
    contractor_id: UUID
    contractor_name: str
    outlet: str
    hourly_rate: float
    year: int
    month: int
    sequence: int = 1
    week1_hours: float
    week2_hours: float
    week3_hours: float
    week4_hours: float
    total_hours: float
    amount: float
    status: str
    sync_status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubmissionBatchOut(BaseModel):
    submission_id: Optional[UUID] = None
    month: int
    year: int
    submitted_at: datetime
    days_count: int
    total_hours: float
    outlets: list[str]
    timesheet_status: str
    rejection_reason: Optional[str] = None
    amount: Optional[float] = None


class BulkApproveRequest(BaseModel):
    timesheet_ids: list[str]


class BulkApproveResult(BaseModel):
    approved: int
    failed: int
    results: list[dict]


# ── Notes ─────────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    contractor_id: str
    content: str
    visibility: str = "internal"


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    visibility: Optional[str] = None


class NoteOut(BaseModel):
    id: UUID
    contractor_id: UUID
    content: str
    visibility: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
