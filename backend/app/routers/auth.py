"""Auth endpoints: signup (individual / school), login, profile, invite acceptance."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..deps import get_current_user
from ..models import (
    ORG_TYPE_INDIVIDUAL,
    ORG_TYPE_SCHOOL,
    ROLE_ORG_ADMIN,
    ROLE_TEACHER,
    Organization,
    OrganizationMember,
    TeacherInvite,
    TeacherSeat,
    User,
)
from ..schemas import (
    IndividualSignupRequest,
    InviteAcceptRequest,
    LoginRequest,
    MembershipOut,
    PasswordChangeRequest,
    ProfileUpdate,
    SchoolSignupRequest,
    TokenResponse,
    UserOut,
)
from ..services.access import ensure_seat_available, get_plan_by_code
from ..services.seed import (
    seed_default_class_subjects,
    seed_default_classes,
    seed_default_subjects,
    unique_slug,
)
from ..models import PaymentRecord

router = APIRouter(prefix="/auth", tags=["auth"])

def _token_response(db: Session, user: User) -> TokenResponse:
    memberships = (
        db.query(OrganizationMember, Organization)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .filter(
            OrganizationMember.user_id == user.id, OrganizationMember.is_active.is_(True)
        )
        .all()
    )
    membership_out = [
        MembershipOut(
            organization_id=org.id,
            organization_name=org.name,
            organization_type=org.org_type,
            role=member.role,
        )
        for member, org in memberships
    ]
    default_org_id = next(
        (org.id for member, org in memberships if org.org_type != ORG_TYPE_INDIVIDUAL),
        memberships[0][1].id if memberships else 0,
    )
    return TokenResponse(
        access_token=create_access_token(subject=user.email, user_id=user.id),
        user=UserOut.model_validate(user),
        memberships=membership_out,
        default_organization_id=default_org_id,
    )


def _create_user(db: Session, email: str, password: str, full_name: str, phone: str | None) -> User:
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please log in instead.",
        )
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        phone=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/signup/individual", response_model=TokenResponse)
def signup_individual(payload: IndividualSignupRequest, db: Session = Depends(get_db)):
    """Individual teacher: free personal workspace (own organization)."""
    user = _create_user(db, payload.email, payload.password, payload.full_name, payload.phone)

    organization = Organization(
        name=f"{payload.full_name.strip()} (Personal)",
        slug=unique_slug(db, f"{payload.full_name}-personal"),
        org_type=ORG_TYPE_INDIVIDUAL,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)

    db.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=ROLE_TEACHER,
        )
    )
    db.commit()
    seed_default_subjects(db, organization.id)
    seed_default_classes(db, organization.id)
    seed_default_class_subjects(db, organization.id)
    return _token_response(db, user)


@router.post("/signup/school", response_model=TokenResponse)
def signup_school(payload: SchoolSignupRequest, db: Session = Depends(get_db)):
    """School owner: creates the school organization and picks a teacher-seat plan."""
    user = _create_user(db, payload.email, payload.password, payload.full_name, payload.phone)
    plan = get_plan_by_code(db, payload.plan_code)

    organization = Organization(
        name=payload.school_name.strip(),
        slug=unique_slug(db, payload.school_name),
        org_type=ORG_TYPE_SCHOOL,
        city=payload.city,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)

    db.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=ROLE_ORG_ADMIN,
        )
    )
    seat = TeacherSeat(
        organization_id=organization.id,
        plan_id=plan.id,
        seats_total=plan.teacher_seats,
        status="active",
        payment_provider="mock",  # MVP sandbox payment; swap for Safepay/PayPro/JazzCash later
        payment_status="mock_paid",
    )
    db.add(seat)
    db.commit()
    db.refresh(seat)

    db.add(
        PaymentRecord(
            organization_id=organization.id,
            seat_id=seat.id,
            amount_pkr=plan.price_pkr,
            provider="mock",
            status="succeeded",
            description=f"{plan.name} (sandbox payment)",
        )
    )
    db.commit()

    seed_default_subjects(db, organization.id)
    seed_default_classes(db, organization.id)
    seed_default_class_subjects(db, organization.id)
    return _token_response(db, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your school owner.",
        )
    return _token_response(db, user)


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response = _token_response(db, user)
    return {
        "user": response.user,
        "memberships": response.memberships,
        "default_organization_id": response.default_organization_id,
    }


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service profile edit: every user can change their own name and phone."""
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if "phone" in payload.model_fields_set:
        user.phone = payload.phone.strip() if payload.phone else None
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password")
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service password change after verifying the current password."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your current password is incorrect.",
        )
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"status": "password changed"}


@router.post("/invites/accept", response_model=TokenResponse)
def accept_invite(payload: InviteAcceptRequest, db: Session = Depends(get_db)):
    """Teacher accepts a school invitation with the invite code."""
    invite = (
        db.query(TeacherInvite)
        .filter(TeacherInvite.invite_code == payload.invite_code.strip().upper())
        .first()
    )
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite code."
        )
    if invite.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This invitation is already {invite.status}.",
        )

    organization = db.get(Organization, invite.organization_id)
    access_msg = "The school has reached its teacher seat limit."
    try:
        ensure_seat_available(db, organization)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=access_msg)

    email = (payload.email or invite.email).lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = _create_user(
            db,
            email,
            payload.password,
            payload.full_name or invite.full_name or email.split("@")[0],
            None,
        )
    else:
        existing_member = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.user_id == user.id,
            )
            .first()
        )
        if existing_member is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This user is already a member of the school.",
            )

    db.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=invite.role or ROLE_TEACHER,
            invited_by_id=invite.created_by_id,
        )
    )
    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return _token_response(db, user)
