"""Access control, teacher seat management and entity lookup helpers."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..deps import OrgContext
from ..models import (
    ORG_TYPE_INDIVIDUAL,
    ROLE_TEACHER,
    SEAT_CONSUMING_ROLES,
    Organization,
    SchoolClass,
    Student,
    Subject,
    SubscriptionPlan,
    TeacherSeat,
    TeacherSubjectAssignment,
    User,
)


# ------------------------------------------------------------------
# Teacher seats
# ------------------------------------------------------------------


def seats_used(db: Session, organization_id: int) -> int:
    from ..models import OrganizationMember

    return (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active.is_(True),
            OrganizationMember.role.in_(SEAT_CONSUMING_ROLES),
        )
        .count()
    )


def get_active_seat(db: Session, organization_id: int) -> TeacherSeat | None:
    return (
        db.query(TeacherSeat)
        .filter(
            TeacherSeat.organization_id == organization_id,
            TeacherSeat.status == "active",
        )
        .order_by(TeacherSeat.id.desc())
        .first()
    )


def students_enrolled(db: Session, organization_id: int) -> int:
    return (
        db.query(Student)
        .filter(
            Student.organization_id == organization_id,
            Student.is_active.is_(True),
        )
        .count()
    )


def seat_usage(db: Session, organization: Organization) -> dict:
    if organization.org_type == ORG_TYPE_INDIVIDUAL:
        return {
            "applies": False,
            "seats_total": 0,
            "seats_used": 0,
            "seats_remaining": 0,
            "student_seats_total": None,
            "student_seats_used": students_enrolled(db, organization.id),
            "plan_code": None,
            "plan_name": "Individual Teacher (Free)",
            "payment_provider": None,
            "payment_status": None,
        }

    seat = get_active_seat(db, organization.id)
    total = seat.seats_total if seat else 0
    used = seats_used(db, organization.id)
    plan = seat.plan if seat else None
    return {
        "applies": True,
        "seats_total": total,
        "seats_used": used,
        "seats_remaining": max(total - used, 0),
        "student_seats_total": plan.student_seats if plan else None,
        "student_seats_used": students_enrolled(db, organization.id),
        "plan_code": plan.code if plan else None,
        "plan_name": plan.name if plan else None,
        "payment_provider": seat.payment_provider if seat else None,
        "payment_status": seat.payment_status if seat else None,
    }


def ensure_seat_available(db: Session, organization: Organization, needed: int = 1) -> None:
    """Raise 402/403 when the school has no free teacher seats left."""
    if organization.org_type == ORG_TYPE_INDIVIDUAL:
        return
    usage = seat_usage(db, organization)
    if usage["seats_remaining"] < needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Teacher seat limit reached ({usage['seats_used']}/{usage['seats_total']}). "
                "Upgrade your plan to invite more teachers."
            ),
        )


def ensure_valid_role(role: str) -> str:
    from ..models import ALL_ROLES

    if role not in ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Allowed: {', '.join(ALL_ROLES)}",
        )
    return role


def get_plan_by_code(db: Session, code: str) -> SubscriptionPlan:
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.code == code, SubscriptionPlan.is_active.is_(True))
        .first()
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown plan code '{code}'"
        )
    return plan


# ------------------------------------------------------------------
# Content access (teachers work on their assigned classes/subjects)
# ------------------------------------------------------------------


def get_teacher_assignments(db: Session, ctx: OrgContext) -> list[TeacherSubjectAssignment]:
    return (
        db.query(TeacherSubjectAssignment)
        .filter(
            TeacherSubjectAssignment.organization_id == ctx.org_id,
            TeacherSubjectAssignment.teacher_id == ctx.user.id,
        )
        .all()
    )


def ensure_teacher_can_access(db: Session, ctx: OrgContext, class_id: int, subject_id: int) -> None:
    """Teachers may only generate/view content for their own assignments.
    Coordinators, principals and school owners can access the whole school."""
    if ctx.member.role != ROLE_TEACHER:
        return
    if ctx.org_type == ORG_TYPE_INDIVIDUAL:
        return  # personal workspace: full access
    assignment = (
        db.query(TeacherSubjectAssignment)
        .filter(
            TeacherSubjectAssignment.organization_id == ctx.org_id,
            TeacherSubjectAssignment.teacher_id == ctx.user.id,
            TeacherSubjectAssignment.class_id == class_id,
            TeacherSubjectAssignment.subject_id == subject_id,
        )
        .first()
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this class and subject. "
            "Please ask your coordinator or school owner to assign you.",
        )


def visible_class_ids_for_teacher(db: Session, ctx: OrgContext) -> list[int] | None:
    """None means 'no restriction' (school-wide roles)."""
    if ctx.member.role != ROLE_TEACHER:
        return None
    if ctx.org_type == ORG_TYPE_INDIVIDUAL:
        return None
    assignments = get_teacher_assignments(db, ctx)
    return sorted({a.class_id for a in assignments})


# ------------------------------------------------------------------
# Entity lookups (used by AI actions to resolve names like "Class 8")
# ------------------------------------------------------------------


def find_class_by_name(db: Session, organization_id: int, value: str | None) -> SchoolClass | None:
    if not value:
        return None
    text = value.strip().lower().replace("class ", "").replace("grade ", "")
    classes = db.query(SchoolClass).filter(SchoolClass.organization_id == organization_id).all()
    for cls in classes:
        if cls.name.lower() == value.strip().lower():
            return cls
    for cls in classes:
        cls_text = cls.name.lower().replace("class ", "").replace("grade ", "")
        if text and text in cls_text:
            return cls
    for cls in classes:
        if cls.grade_level is not None and str(cls.grade_level) == text:
            return cls
    return None


def find_subject_by_name(db: Session, organization_id: int, value: str | None) -> Subject | None:
    if not value:
        return None
    text = value.strip().lower()
    subjects = db.query(Subject).filter(Subject.organization_id == organization_id).all()
    for subject in subjects:
        if subject.name.lower() == text or (subject.code or "").lower() == text:
            return subject
    for subject in subjects:
        if text in subject.name.lower():
            return subject
    return None


def find_student_by_name(db: Session, organization_id: int, value: str | None) -> Student | None:
    if not value:
        return None
    return (
        db.query(Student)
        .filter(
            Student.organization_id == organization_id,
            Student.is_active.is_(True),
            Student.name.ilike(f"%{value.strip()}%"),
        )
        .first()
    )


def find_teacher_by_name(db: Session, organization_id: int, value: str | None) -> User | None:
    if not value:
        return None
    from ..models import OrganizationMember

    return (
        db.query(User)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active.is_(True),
            User.full_name.ilike(f"%{value.strip()}%"),
        )
        .first()
    )
