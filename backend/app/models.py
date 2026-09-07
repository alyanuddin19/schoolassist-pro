"""SchoolAssist database models.

Multi-tenant SaaS schema: every school-owned table carries `organization_id`
so data is always scoped to one organization (school or individual teacher).
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base

# ------------------------------------------------------------------
# Roles (organization membership roles)
# ------------------------------------------------------------------
ROLE_ORG_ADMIN = "org_admin"            # School Owner / Organization Admin
ROLE_PRINCIPAL = "principal"            # Principal / Academic Head
ROLE_VICE_PRINCIPAL = "vice_principal"  # Vice Principal / Deputy Head
ROLE_COORDINATOR = "subject_coordinator"  # Subject / Academic Coordinator
ROLE_TEACHER = "teacher"                # Teacher (or Individual Teacher)

ALL_ROLES = (ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR, ROLE_TEACHER)
# Roles that consume a teacher seat in a school plan
SEAT_CONSUMING_ROLES = (ROLE_TEACHER, ROLE_COORDINATOR, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL)

# ------------------------------------------------------------------
# Organization types
# ------------------------------------------------------------------
ORG_TYPE_SCHOOL = "school"
ORG_TYPE_INDIVIDUAL = "individual"

# ------------------------------------------------------------------
# Test types
# ------------------------------------------------------------------
TEST_TYPE_WEEKLY = "weekly"
TEST_TYPE_MONTHLY = "monthly"
TEST_TYPE_MID_TERM = "mid_term"
TEST_TYPE_FINAL_TERM = "final_term"
ALL_TEST_TYPES = (TEST_TYPE_WEEKLY, TEST_TYPE_MONTHLY, TEST_TYPE_MID_TERM, TEST_TYPE_FINAL_TERM)

# Report types
REPORT_TYPE_STUDENT = "student"
REPORT_TYPE_SUBJECT = "subject"
REPORT_TYPE_CLASS = "class"
REPORT_TYPE_FINAL_TERM = "final_term"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(140), unique=True, nullable=False, index=True)
    org_type = Column(String(30), nullable=False, default=ORG_TYPE_SCHOOL)
    city = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("OrganizationMember", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship(
        "OrganizationMember",
        back_populates="user",
        # organization_members has two FKs to users (user_id, invited_by_id)
        foreign_keys="OrganizationMember.user_id",
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(40), nullable=False, default=ROLE_TEACHER)
    is_active = Column(Boolean, nullable=False, default=True)
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships", foreign_keys=[user_id])


class Teacher(Base):
    """School-scoped profile data kept separate from authentication users."""
    __tablename__ = "teachers"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_id", name="uq_teacher_org_employee_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    employee_id = Column(String(60), nullable=False)
    designation = Column(String(120), nullable=False)
    # "primary" (classes 1-5) or "secondary" (6-10); null means both / not set.
    level = Column(String(20), nullable=True)
    gender = Column(String(30), nullable=True)
    qualification = Column(String(150), nullable=True)
    department = Column(String(120), nullable=True)
    profile_photo = Column(String(500), nullable=True)
    joining_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TeacherSubject(Base):
    """Subjects a teacher is qualified / allowed to teach."""

    __tablename__ = "teacher_subjects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "teacher_id", "subject_id", name="uq_teacher_subject"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    teacher_seats = Column(Integer, nullable=False)
    # How many active students the plan covers; null means unlimited.
    student_seats = Column(Integer, nullable=True)
    price_pkr = Column(Float, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="PKR")
    billing_period = Column(String(30), nullable=False, default="monthly")
    features = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TeacherSeat(Base):
    """Current seat allocation / subscription instance for an organization."""

    __tablename__ = "teacher_seats"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    seats_total = Column(Integer, nullable=False, default=0)
    status = Column(String(40), nullable=False, default="active")
    payment_provider = Column(String(40), nullable=False, default="mock")
    payment_status = Column(String(40), nullable=False, default="mock_paid")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("SubscriptionPlan")


class PaymentRecord(Base):
    """Payments. Mocked for MVP; provider field is ready for Safepay,
    PayPro, JazzCash or manual invoice approval later."""

    __tablename__ = "payment_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    seat_id = Column(Integer, ForeignKey("teacher_seats.id"), nullable=True)
    amount_pkr = Column(Float, nullable=False, default=0)
    provider = Column(String(40), nullable=False, default="mock")
    provider_reference = Column(String(200), nullable=True)
    status = Column(String(40), nullable=False, default="succeeded")
    description = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TeacherInvite(Base):
    __tablename__ = "teacher_invites"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(150), nullable=True)
    role = Column(String(40), nullable=False, default=ROLE_TEACHER)
    status = Column(String(40), nullable=False, default="pending")  # pending/accepted/revoked
    invite_code = Column(String(64), unique=True, nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)


class SchoolClass(Base):
    """A class / grade, e.g. "Class 8"."""

    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    grade_level = Column(Integer, nullable=True)
    # Optional per-class strength limit; NULL means the school set no cap.
    capacity = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sections = relationship("Section", back_populates="school_class")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    class_teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    school_class = relationship("SchoolClass", back_populates="sections")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClassSubject(Base):
    """Which subjects are taught in which class (per-class subject list)."""

    __tablename__ = "class_subjects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "class_id", "subject_id", name="uq_class_subject_org_class_subject"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        Index("ix_students_org_class_roll", "organization_id", "class_id", "roll_no"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True, index=True)
    roll_no = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False, index=True)
    guardian_name = Column(String(150), nullable=True)
    guardian_phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Guardian(Base):
    """Reusable parent/guardian record; one guardian may link to many students."""
    __tablename__ = "guardians"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentGuardian(Base):
    __tablename__ = "student_guardians"
    __table_args__ = (UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),)
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    guardian_id = Column(Integer, ForeignKey("guardians.id"), nullable=False, index=True)
    relationship = Column(String(60), nullable=True)


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(250), nullable=False)
    message = Column(Text, nullable=False)
    audience = Column(String(60), nullable=False, default="school")
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    published_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)


class SchoolSetting(Base):
    __tablename__ = "school_settings"
    organization_id = Column(Integer, ForeignKey("organizations.id"), primary_key=True)
    academic_year = Column(String(30), nullable=True)
    working_days = Column(JSON, nullable=True)
    school_start_time = Column(String(10), nullable=True)
    school_end_time = Column(String(10), nullable=True)
    period_minutes = Column(Integer, nullable=True)
    logo = Column(String(500), nullable=True)


class StudentAttendance(Base):
    """Daily student attendance marked per class/section."""

    __tablename__ = "student_attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_student_attendance_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    status = Column(String(20), nullable=False, default="present")  # present/absent/leave/late
    marked_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TeacherAttendance(Base):
    """Daily staff attendance (check-in / status) for teachers and staff."""

    __tablename__ = "teacher_attendance"
    __table_args__ = (
        UniqueConstraint("organization_id", "teacher_id", "date", name="uq_teacher_attendance_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    status = Column(String(20), nullable=False, default="present")  # present/absent/leave/late
    check_in = Column(String(10), nullable=True)
    check_out = Column(String(10), nullable=True)
    marked_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TeacherLeave(Base):
    """A staff leave request; the principal approves or rejects it."""

    __tablename__ = "teacher_leaves"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    reason = Column(String(300), nullable=False)
    # pending / approved / rejected
    status = Column(String(20), nullable=False, default="pending", index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LeaveSubstitution(Base):
    """One covered period/class/day arranged while a leave is in force."""

    __tablename__ = "leave_substitutions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    leave_id = Column(Integer, ForeignKey("teacher_leaves.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    substitute_teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TimetableEntry(Base):
    """One weekly period: class/section + subject + teacher + day + time slot."""

    __tablename__ = "timetable_entries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    day = Column(String(10), nullable=False, index=True)  # Monday ... Saturday
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    approval_status = Column(String(30), nullable=False, default="draft")
    approval_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamSchedule(Base):
    """Exam timetable row: one subject paper for a class on a date/time slot."""

    __tablename__ = "exam_schedules"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    term = Column(String(40), nullable=False, index=True)  # Mid Term / Final Term ...
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_status = Column(String(30), nullable=False, default="draft")
    approval_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamRoom(Base):
    """Examination room with seating capacity."""

    __tablename__ = "exam_rooms"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    capacity = Column(Integer, nullable=False, default=30)


class SeatingPlan(Base):
    """Generated room allocation for one term; null class means all classes."""

    __tablename__ = "seating_plans"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    term = Column(String(40), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True, index=True)
    # "primary"/"secondary" when the plan was generated for one school level.
    level = Column(String(20), nullable=True)
    # How many different classes one room may hold; null means fully mixed.
    classes_per_room = Column(Integer, nullable=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    assignments = relationship(
        "SeatingAssignment", back_populates="plan", cascade="all, delete-orphan"
    )


class SeatingAssignment(Base):
    __tablename__ = "seating_assignments"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("seating_plans.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("exam_rooms.id"), nullable=False, index=True)
    seat_no = Column(Integer, nullable=False, default=1)

    plan = relationship("SeatingPlan", back_populates="assignments")
    room = relationship("ExamRoom")
    student = relationship("Student")


class TeacherSubjectAssignment(Base):
    """Which teacher teaches which subject in which class/section."""

    __tablename__ = "teacher_subject_assignments"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    academic_year = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Worksheet(Base):
    __tablename__ = "worksheets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    title = Column(String(250), nullable=False)
    topic = Column(String(300), nullable=True)
    instructions = Column(Text, nullable=True)
    difficulty = Column(String(40), nullable=True)
    language = Column(String(30), nullable=False, default="en")
    question_types = Column(JSON, nullable=True)
    content = Column(Text, nullable=True)
    answer_key = Column(Text, nullable=True)
    marking_scheme = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Test(Base):
    """Weekly test / monthly test / mid term / final term papers."""

    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    test_type = Column(String(30), nullable=False, default=TEST_TYPE_WEEKLY, index=True)
    title = Column(String(250), nullable=False)
    topic = Column(String(300), nullable=True)
    total_marks = Column(Integer, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    language = Column(String(30), nullable=False, default="en")
    content = Column(Text, nullable=True)
    answer_key = Column(Text, nullable=True)
    marking_scheme = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Marksheet(Base):
    __tablename__ = "marksheets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=True)
    title = Column(String(250), nullable=False)
    exam_type = Column(String(40), nullable=True)
    total_marks = Column(Float, nullable=False, default=100)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_file_name = Column(String(255), nullable=True)
    status = Column(String(40), nullable=False, default="ready")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    entries = relationship(
        "MarksheetEntry", back_populates="marksheet", cascade="all, delete-orphan"
    )


class MarksheetEntry(Base):
    __tablename__ = "marksheet_entries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    marksheet_id = Column(Integer, ForeignKey("marksheets.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    obtained_marks = Column(Float, nullable=False, default=0)
    total_marks = Column(Float, nullable=False, default=100)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    marksheet = relationship("Marksheet", back_populates="entries")
    student = relationship("Student")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    report_type = Column(String(40), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    academic_year = Column(String(30), nullable=True)
    title = Column(String(250), nullable=False)
    content = Column(JSON, nullable=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(250), nullable=True)
    language = Column(String(30), nullable=False, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=True)
    action = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiAction(Base):
    """Audit log of every tool/action triggered through the AI assistant."""

    __tablename__ = "ai_actions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("ai_chat_sessions.id"), nullable=True)
    action_name = Column(String(80), nullable=False, index=True)
    params = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="success")
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
