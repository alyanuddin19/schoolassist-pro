from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import ALL_ROLES, ALL_TEST_TYPES

# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------


class IndividualSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=2, max_length=150)
    phone: Optional[str] = None


class SchoolSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=2, max_length=150)
    phone: Optional[str] = None
    school_name: str = Field(min_length=2, max_length=200)
    city: Optional[str] = None
    plan_code: str = Field(default="seats_25")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class InviteAcceptRequest(BaseModel):
    invite_code: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: str = Field(min_length=6, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None


class MembershipOut(BaseModel):
    organization_id: int
    organization_name: str
    organization_type: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    memberships: list[MembershipOut]
    default_organization_id: int


# ------------------------------------------------------------------
# Organizations, seats and members
# ------------------------------------------------------------------


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    teacher_seats: int
    price_pkr: float
    currency: str
    billing_period: str
    features: Optional[Any] = None


class SeatUsageOut(BaseModel):
    applies: bool
    seats_total: int
    seats_used: int
    seats_remaining: int
    student_seats_total: Optional[int] = None
    student_seats_used: int = 0
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    payment_provider: Optional[str] = None
    payment_status: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Self-service account edit; sending phone as null clears it."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=50)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=100)


class MemberCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    role: str = Field(default="teacher")
    password: Optional[str] = Field(default=None, min_length=6, max_length=100)


class MemberUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class InviteCreateRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = Field(default="teacher")


class ChangePlanRequest(BaseModel):
    plan_code: str


class MemberOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    joined_at: Optional[datetime] = None
    temporary_password: Optional[str] = None


class InviteOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    status: str
    invite_code: str
    created_at: Optional[datetime] = None


# ------------------------------------------------------------------
# Academics
# ------------------------------------------------------------------


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    grade_level: Optional[int] = None
    capacity: Optional[int] = Field(default=None, ge=1)


class ClassUpdate(BaseModel):
    """Partial class edit. A field sent as null clears it (capacity, grade level)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    grade_level: Optional[int] = None
    capacity: Optional[int] = Field(default=None, ge=1)


class SectionCreate(BaseModel):
    class_id: int
    name: str = Field(min_length=1, max_length=60)
    class_teacher_id: Optional[int] = None


class SectionUpdate(BaseModel):
    """Partial section edit; null clears the class teacher."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    class_teacher_id: Optional[int] = None


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: Optional[str] = None


class SubjectUpdate(BaseModel):
    """Partial subject edit; sending ``code: null`` clears the short code."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    code: Optional[str] = Field(default=None, max_length=40)


class ClassSubjectsUpdate(BaseModel):
    subject_ids: list[int] = Field(default_factory=list)


class StudentCreate(BaseModel):
    class_id: int
    section_id: Optional[int] = None
    roll_no: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None


class StudentUpdate(BaseModel):
    class_id: Optional[int] = None
    section_id: Optional[int] = None
    roll_no: Optional[str] = None
    name: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: Optional[str] = None
    role: str = Field(default="teacher")
    designation: str = Field(default="Teacher")
    # "primary" (classes 1-5) or "secondary" (6-10); blank means both.
    level: Optional[str] = None
    qualification: Optional[str] = None
    department: Optional[str] = None
    gender: Optional[str] = None
    joining_date: Optional[str] = None
    subject_ids: list[int] = Field(default_factory=list)
    password: Optional[str] = Field(default=None, min_length=6, max_length=100)
    send_email: bool = False


class TeacherUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    designation: Optional[str] = None
    level: Optional[str] = None
    qualification: Optional[str] = None
    department: Optional[str] = None
    gender: Optional[str] = None
    joining_date: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherSubjectsUpdate(BaseModel):
    subject_ids: list[int] = Field(default_factory=list)


class GuardianCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: Optional[str] = None
    email: Optional[str] = None


class GuardianUpdate(BaseModel):
    """Partial guardian edit; sending phone/email as null clears them."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    phone: Optional[str] = None
    email: Optional[str] = None


class StudentGuardianLink(BaseModel):
    guardian_id: Optional[int] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relationship: Optional[str] = None


class TeacherAssignmentCreate(BaseModel):
    teacher_id: int
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    academic_year: Optional[str] = None


class StudentImportRow(BaseModel):
    roll_no: str
    name: str
    section_name: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None


# ------------------------------------------------------------------
# Generation (worksheets & tests)
# ------------------------------------------------------------------


class QuestionCounts(BaseModel):
    mcq: int = Field(default=5, ge=0, le=30)
    short: int = Field(default=3, ge=0, le=20)
    long: int = Field(default=1, ge=0, le=10)


class WorksheetGenerateRequest(BaseModel):
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    topic: str = Field(min_length=2, max_length=300)
    title: Optional[str] = None
    instructions: Optional[str] = None
    difficulty: str = Field(default="medium")
    language: str = Field(default="en")  # en | ur | roman_urdu
    question_counts: QuestionCounts = QuestionCounts()


class TestGenerateRequest(BaseModel):
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    test_type: str = Field(default="weekly")
    topic: Optional[str] = None
    title: Optional[str] = None
    total_marks: int = Field(default=50, ge=5, le=300)
    duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    difficulty: str = Field(default="medium")
    language: str = Field(default="en")
    question_counts: QuestionCounts = QuestionCounts()


# ------------------------------------------------------------------
# Marksheets
# ------------------------------------------------------------------


class MarksheetEntryIn(BaseModel):
    student_id: int
    obtained_marks: float
    remarks: Optional[str] = None


class MarksheetManualRequest(BaseModel):
    class_id: int
    section_id: Optional[int] = None
    subject_id: int
    test_id: Optional[int] = None
    title: str
    exam_type: Optional[str] = None
    total_marks: float = 100
    entries: list[MarksheetEntryIn]


# ------------------------------------------------------------------
# Reports
# ------------------------------------------------------------------


class FinalTermReportRequest(BaseModel):
    class_id: int
    section_id: Optional[int] = None
    title: Optional[str] = None
    academic_year: Optional[str] = None


# ------------------------------------------------------------------
# AI Chat
# ------------------------------------------------------------------


class ChatHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatHistoryItem] = Field(default_factory=list)
    language: str = Field(default="en")  # en | ur | roman_urdu
    current_page: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None
    session_id: Optional[int] = None


class ChatActionInfo(BaseModel):
    name: str
    params: Optional[dict] = None


class ChatResponse(BaseModel):
    session_id: int
    reply: str
    action: Optional[ChatActionInfo] = None
    action_status: Optional[str] = None
    action_result: Optional[Any] = None
