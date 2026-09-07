"""Organization management: members, invites, teacher seats, plans and payments."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import OrgContext, get_org_context, require_roles
from ..models import (
    ORG_TYPE_INDIVIDUAL,
    ROLE_ORG_ADMIN,
    OrganizationMember,
    PaymentRecord,
    SubscriptionPlan,
    TeacherInvite,
    TeacherSeat,
    Teacher,
    User,
)
from ..schemas import (
    ChangePlanRequest,
    InviteCreateRequest,
    InviteOut,
    MemberCreateRequest,
    MemberOut,
    MemberUpdateRequest,
    PlanOut,
    SeatUsageOut,
)
from ..core.security import hash_password
from ..services.access import (
    ensure_seat_available,
    ensure_valid_role,
    get_plan_by_code,
    seat_usage,
    seats_used,
)

router = APIRouter(prefix="/org", tags=["organization"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """Public list of teacher-seat plans (used by the signup wizard)."""
    return (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.teacher_seats)
        .all()
    )


@router.get("/overview")
def org_overview(ctx: OrgContext = Depends(get_org_context)):
    from ..models import Marksheet, Report, SchoolClass, Section, Student, Subject, Test, Worksheet

    db = ctx.db
    org = ctx.organization
    counts = {
        "classes": db.query(SchoolClass).filter(SchoolClass.organization_id == org.id).count(),
        "sections": db.query(Section).filter(Section.organization_id == org.id).count(),
        "subjects": db.query(Subject).filter(Subject.organization_id == org.id).count(),
        "students": db.query(Student).filter(Student.organization_id == org.id).count(),
        "worksheets": db.query(Worksheet).filter(Worksheet.organization_id == org.id).count(),
        "tests": db.query(Test).filter(Test.organization_id == org.id).count(),
        "marksheets": db.query(Marksheet).filter(Marksheet.organization_id == org.id).count(),
        "reports": db.query(Report).filter(Report.organization_id == org.id).count(),
    }
    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "type": org.org_type,
            "city": org.city,
            "created_at": org.created_at.isoformat() if org.created_at else None,
        },
        "role": ctx.role,
        "seats": seat_usage(db, org),
        "counts": counts,
    }


@router.get("/seats", response_model=SeatUsageOut)
def seats_overview(ctx: OrgContext = Depends(get_org_context)):
    return seat_usage(ctx.db, ctx.organization)


class OrgProfileUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    phone: str | None = None


@router.patch("/profile")
def update_org_profile(
    payload: OrgProfileUpdate,
    ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN)),
):
    """School name / contact details (School Settings page)."""
    org = ctx.organization
    if payload.name is not None and payload.name.strip():
        org.name = payload.name.strip()
    if payload.city is not None:
        org.city = payload.city.strip() or None
    if payload.phone is not None:
        org.phone = payload.phone.strip() or None
    ctx.db.commit()
    return {"id": org.id, "name": org.name, "city": org.city, "phone": org.phone}


@router.get("/members", response_model=list[MemberOut])
def list_members(ctx: OrgContext = Depends(get_org_context)):
    rows = (
        ctx.db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == ctx.org_id)
        .order_by(OrganizationMember.joined_at.asc())
        .all()
    )
    return [
        MemberOut(
            id=member.id,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]


@router.post("/members", response_model=MemberOut)
def create_member(
    payload: MemberCreateRequest,
    ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN)),
):
    """School owner directly creates a staff account (seat limit enforced)."""
    ensure_valid_role(payload.role)
    ensure_seat_available(ctx.db, ctx.organization)

    email = payload.email.lower()
    user = ctx.db.query(User).filter(User.email == email).first()
    generated_password = None
    if user is None:
        generated_password = payload.password or secrets.token_urlsafe(8)
        user = User(
            email=email,
            hashed_password=hash_password(generated_password),
            full_name=payload.full_name.strip(),
        )
        ctx.db.add(user)
        ctx.db.commit()
        ctx.db.refresh(user)

    existing = (
        ctx.db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == ctx.org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user is already a member of your school.",
        )

    member = OrganizationMember(
        organization_id=ctx.org_id,
        user_id=user.id,
        role=payload.role,
        invited_by_id=ctx.user.id,
    )
    ctx.db.add(member)
    # Every staff account gets a school profile so it shows in the staff
    # roster, the attendance register and the leave desk.
    staff_designations = {
        "teacher": "Teacher",
        "subject_coordinator": "Subject Coordinator",
        "principal": "Principal",
        "vice_principal": "Vice Principal",
    }
    designation = staff_designations.get(payload.role)
    if designation:
        employee_id = f"T-{ctx.org_id}-{secrets.token_hex(3).upper()}"
        while ctx.db.query(Teacher).filter(Teacher.organization_id == ctx.org_id, Teacher.employee_id == employee_id).first():
            employee_id = f"T-{ctx.org_id}-{secrets.token_hex(3).upper()}"
        ctx.db.add(Teacher(organization_id=ctx.org_id, user_id=user.id, employee_id=employee_id, designation=designation, status="active"))
    ctx.db.commit()
    ctx.db.refresh(member)

    result = MemberOut(
        id=member.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=member.role,
        is_active=member.is_active,
        joined_at=member.joined_at,
    )
    # Surface one-time credentials so the owner can share them securely
    result_dict = result.model_dump()
    if generated_password:
        result_dict["temporary_password"] = generated_password
    return result_dict


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(
    member_id: int,
    payload: MemberUpdateRequest,
    ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN)),
):
    member = (
        ctx.db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == ctx.org_id,
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if member.user_id == ctx.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role or status.",
        )

    if payload.role is not None:
        ensure_valid_role(payload.role)
        member.role = payload.role
    if payload.is_active is not None:
        member.is_active = payload.is_active
    ctx.db.commit()
    ctx.db.refresh(member)

    user = ctx.db.get(User, member.user_id)
    return MemberOut(
        id=member.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=member.role,
        is_active=member.is_active,
        joined_at=member.joined_at,
    )


@router.delete("/members/{member_id}")
def deactivate_member(
    member_id: int, ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN))
):
    """Deactivate a member - this frees a teacher seat."""
    member = (
        ctx.db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == ctx.org_id,
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if member.user_id == ctx.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    member.is_active = False
    ctx.db.commit()
    usage = seat_usage(ctx.db, ctx.organization)
    return {"status": "deactivated", "seats": usage}


@router.get("/invites", response_model=list[InviteOut])
def list_invites(ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN))):
    invites = (
        ctx.db.query(TeacherInvite)
        .filter(TeacherInvite.organization_id == ctx.org_id)
        .order_by(TeacherInvite.created_at.desc())
        .all()
    )
    return [
        InviteOut(
            id=i.id,
            email=i.email,
            full_name=i.full_name,
            role=i.role,
            status=i.status,
            invite_code=i.invite_code,
            created_at=i.created_at,
        )
        for i in invites
    ]


@router.post("/invites", response_model=InviteOut)
def create_invite(
    payload: InviteCreateRequest,
    ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN)),
):
    if ctx.is_individual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Individual teacher accounts cannot invite members.",
        )
    ensure_valid_role(payload.role)
    ensure_seat_available(ctx.db, ctx.organization)

    invite = TeacherInvite(
        organization_id=ctx.org_id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        role=payload.role,
        invite_code=secrets.token_hex(6).upper(),
        created_by_id=ctx.user.id,
    )
    ctx.db.add(invite)
    ctx.db.commit()
    ctx.db.refresh(invite)
    return InviteOut(
        id=invite.id,
        email=invite.email,
        full_name=invite.full_name,
        role=invite.role,
        status=invite.status,
        invite_code=invite.invite_code,
        created_at=invite.created_at,
    )


@router.delete("/invites/{invite_id}")
def revoke_invite(
    invite_id: int, ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN))
):
    invite = (
        ctx.db.query(TeacherInvite)
        .filter(
            TeacherInvite.id == invite_id,
            TeacherInvite.organization_id == ctx.org_id,
        )
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    if invite.status == "pending":
        invite.status = "revoked"
        ctx.db.commit()
    return {"status": invite.status}


@router.post("/subscription/change-plan")
def change_plan(
    payload: ChangePlanRequest,
    ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN)),
):
    """Switch to another teacher-seat plan. Payment is mocked for the MVP:
    the provider field is ready for Safepay / PayPro / JazzCash / manual invoice."""
    plan = get_plan_by_code(ctx.db, payload.plan_code)

    seat = (
        ctx.db.query(TeacherSeat)
        .filter(TeacherSeat.organization_id == ctx.org_id, TeacherSeat.status == "active")
        .order_by(TeacherSeat.id.desc())
        .first()
    )
    if seat is None:
        seat = TeacherSeat(organization_id=ctx.org_id)
        ctx.db.add(seat)

    used = seats_used(ctx.db, ctx.org_id)
    if plan.teacher_seats < used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"You currently have {used} active teachers. "
                f"Choose a plan with at least {used} seats."
            ),
        )

    seat.plan_id = plan.id
    seat.seats_total = plan.teacher_seats
    seat.payment_provider = "mock"
    seat.payment_status = "mock_paid"
    ctx.db.commit()

    ctx.db.add(
        PaymentRecord(
            organization_id=ctx.org_id,
            seat_id=seat.id,
            amount_pkr=plan.price_pkr,
            provider="mock",
            status="succeeded",
            description=f"Plan changed to {plan.name} (sandbox payment)",
        )
    )
    ctx.db.commit()
    return {"plan": plan.code, "seats": seat_usage(ctx.db, ctx.organization)}


@router.get("/payments")
def list_payments(ctx: OrgContext = Depends(require_roles(ROLE_ORG_ADMIN))):
    payments = (
        ctx.db.query(PaymentRecord)
        .filter(PaymentRecord.organization_id == ctx.org_id)
        .order_by(PaymentRecord.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "amount_pkr": p.amount_pkr,
            "provider": p.provider,
            "status": p.status,
            "description": p.description,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments
    ]
