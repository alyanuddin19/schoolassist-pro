"""School-level announcements and academic-year settings."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..deps import OrgContext, get_org_context
from ..models import Announcement, SchoolSetting, ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR

router = APIRouter(prefix="/school", tags=["school"])

class AnnouncementIn(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    message: str = Field(min_length=2)
    audience: str = "school"
    class_id: int | None = None
    section_id: int | None = None
class SettingsIn(BaseModel):
    academic_year: str | None = None
    working_days: list[str] = []
    school_start_time: str | None = None
    school_end_time: str | None = None
    period_minutes: int | None = None

@router.get("/announcements")
def announcements(ctx: OrgContext = Depends(get_org_context)):
    return [{"id": x.id, "title": x.title, "message": x.message, "audience": x.audience, "class_id": x.class_id, "section_id": x.section_id, "published_at": x.published_at.isoformat() if x.published_at else None} for x in ctx.db.query(Announcement).filter(Announcement.organization_id == ctx.org_id).order_by(Announcement.published_at.desc()).all()]

@router.post("/announcements")
def create_announcement(payload: AnnouncementIn, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in (ROLE_ORG_ADMIN, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR, ROLE_PRINCIPAL): raise HTTPException(403, "Your role cannot publish announcements.")
    row = Announcement(organization_id=ctx.org_id, **payload.model_dump()); ctx.db.add(row); ctx.db.commit(); ctx.db.refresh(row)
    return {"id": row.id, **payload.model_dump(), "published_at": row.published_at.isoformat() if row.published_at else None}

@router.get("/settings")
def get_settings(ctx: OrgContext = Depends(get_org_context)):
    row = ctx.db.get(SchoolSetting, ctx.org_id)
    return {"academic_year": row.academic_year if row else None, "working_days": row.working_days if row and row.working_days else [], "school_start_time": row.school_start_time if row else None, "school_end_time": row.school_end_time if row else None, "period_minutes": row.period_minutes if row else None, "logo": row.logo if row else None}

@router.put("/settings")
def update_settings(payload: SettingsIn, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role != ROLE_ORG_ADMIN: raise HTTPException(403, "Only the admin can update school setup.")
    row = ctx.db.get(SchoolSetting, ctx.org_id) or SchoolSetting(organization_id=ctx.org_id)
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    ctx.db.add(row); ctx.db.commit(); return get_settings(ctx)
