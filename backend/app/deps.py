"""FastAPI dependencies: JWT auth + multi-tenant organization scoping."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .core.security import decode_access_token
from .database import get_db
from .models import (
    ORG_TYPE_INDIVIDUAL,
    ROLE_COORDINATOR,
    ROLE_ORG_ADMIN,
    ROLE_PRINCIPAL,
    ROLE_VICE_PRINCIPAL,
    Organization,
    OrganizationMember,
    User,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("uid")
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user


@dataclass
class OrgContext:
    """Resolved tenant context: the acting user inside one organization."""

    user: User
    organization: Organization
    member: OrganizationMember
    db: Session

    @property
    def role(self) -> str:
        return self.member.role

    @property
    def org_id(self) -> int:
        return self.organization.id

    @property
    def org_type(self) -> str:
        return self.organization.org_type

    @property
    def is_school(self) -> bool:
        return self.organization.org_type != ORG_TYPE_INDIVIDUAL

    @property
    def is_individual(self) -> bool:
        return self.organization.org_type == ORG_TYPE_INDIVIDUAL

    @property
    def is_owner(self) -> bool:
        return self.member.role == ROLE_ORG_ADMIN

    @property
    def is_academic_lead(self) -> bool:
        return self.member.role in (
            ROLE_ORG_ADMIN,
            ROLE_PRINCIPAL,
            ROLE_VICE_PRINCIPAL,
            ROLE_COORDINATOR,
        )


def get_org_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgContext:
    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id, OrganizationMember.is_active.is_(True))
        .all()
    )
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of any organization yet",
        )

    header_org = request.headers.get("x-organization-id")
    selected = None
    if header_org:
        try:
            header_org_id = int(header_org)
        except ValueError:
            header_org_id = None
        if header_org_id:
            selected = next(
                (m for m in memberships if m.organization_id == header_org_id), None
            )
            if selected is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to the requested organization",
                )
    if selected is None:
        # Default: prefer a school organization over a personal workspace
        selected = next(
            (m for m in memberships if m.organization.org_type != ORG_TYPE_INDIVIDUAL),
            memberships[0],
        )

    organization = db.get(Organization, selected.organization_id)
    return OrgContext(user=user, organization=organization, member=selected, db=db)


def require_roles(*roles: str):
    """Dependency factory restricting an endpoint to specific roles."""

    def dependency(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
        if ctx.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not allow this action",
            )
        return ctx

    return dependency
