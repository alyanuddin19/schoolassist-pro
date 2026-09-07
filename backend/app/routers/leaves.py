"""Staff leave workflow: teacher request → VP review → principal decision."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..database import get_db
from ..deps import OrgContext, get_org_context
from ..models import (LeaveSubstitution, SchoolClass, Subject, TeacherLeave, User,
                      ROLE_COORDINATOR, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL)

router = APIRouter(prefix="/leaves", tags=["leaves"])

class LeaveCreate(BaseModel):
    teacher_id: int | None = None
    start_date: str
    end_date: str
    reason: str = Field(min_length=2, max_length=300)

class Decision(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=300)

class Substitution(BaseModel):
    date: str
    class_id: int
    subject_id: int | None = None
    substitute_teacher_id: int
    note: str | None = Field(default=None, max_length=200)

def _row(ctx: OrgContext, leave: TeacherLeave):
    users = {u.id: u.full_name for u in ctx.db.query(User).all()}
    classes = {c.id: c.name for c in ctx.db.query(SchoolClass).filter(SchoolClass.organization_id == ctx.org_id)}
    subjects = {s.id: s.name for s in ctx.db.query(Subject).filter(Subject.organization_id == ctx.org_id)}
    subs = ctx.db.query(LeaveSubstitution).filter(LeaveSubstitution.leave_id == leave.id).all()
    days = (datetime.fromisoformat(leave.end_date).date() - datetime.fromisoformat(leave.start_date).date()).days + 1
    return {"id": leave.id, "teacher_id": leave.teacher_id, "teacher": users.get(leave.teacher_id, ""),
            "start_date": leave.start_date, "end_date": leave.end_date, "days": max(days, 1),
            "reason": leave.reason, "status": leave.status,
            "requested_by": users.get(leave.requested_by_id), "decided_by": users.get(leave.decided_by_id),
            "decided_at": leave.decided_at.isoformat() if leave.decided_at else None,
            "decision_note": leave.decision_note,
            "created_at": leave.created_at.isoformat() if leave.created_at else None,
            "substitutions": [{"id": s.id, "date": s.date, "class_id": s.class_id,
              "class": classes.get(s.class_id, ""), "subject_id": s.subject_id,
              "subject": subjects.get(s.subject_id) if s.subject_id else None,
              "substitute_teacher_id": s.substitute_teacher_id, "substitute": users.get(s.substitute_teacher_id, ""), "note": s.note} for s in subs]}

@router.get("")
def list_leaves(status: str | None = None, ctx: OrgContext = Depends(get_org_context)):
    query = ctx.db.query(TeacherLeave).filter(TeacherLeave.organization_id == ctx.org_id)
    if ctx.role not in (ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR): query = query.filter(TeacherLeave.teacher_id == ctx.user.id)
    if status: query = query.filter(TeacherLeave.status == status)
    return [_row(ctx, x) for x in query.order_by(TeacherLeave.created_at.desc()).all()]

@router.post("")
def create_leave(payload: LeaveCreate, ctx: OrgContext = Depends(get_org_context)):
    teacher_id = ctx.user.id
    if payload.end_date < payload.start_date: raise HTTPException(400, "End date must not be before start date.")
    leave = TeacherLeave(organization_id=ctx.org_id, teacher_id=teacher_id, requested_by_id=ctx.user.id,
                         start_date=payload.start_date, end_date=payload.end_date, reason=payload.reason,
                         status="pending_principal_approval")
    ctx.db.add(leave); ctx.db.commit(); ctx.db.refresh(leave)
    return _row(ctx, leave)

@router.patch("/{leave_id}/decision")
def decide_leave(leave_id: int, payload: Decision, ctx: OrgContext = Depends(get_org_context)):
    leave = ctx.db.query(TeacherLeave).filter(TeacherLeave.id == leave_id, TeacherLeave.organization_id == ctx.org_id).first()
    if not leave: raise HTTPException(404, "Leave request not found.")
    if ctx.role == ROLE_PRINCIPAL:
        if leave.status != "pending_principal_approval" or payload.status not in ("approved", "rejected"):
            raise HTTPException(400, "Principal can approve or reject a VP-reviewed request.")
        leave.status = payload.status
    else: raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the principal can approve or reject leave.")
    leave.decided_by_id = ctx.user.id; leave.decided_at = datetime.utcnow(); leave.decision_note = payload.note
    ctx.db.commit(); ctx.db.refresh(leave); return _row(ctx, leave)

@router.post("/{leave_id}/substitutions")
def add_substitution(leave_id: int, payload: Substitution, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in (ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR): raise HTTPException(403, "Only VP/coordinator can assign substitutes.")
    leave = ctx.db.query(TeacherLeave).filter(TeacherLeave.id == leave_id, TeacherLeave.organization_id == ctx.org_id).first()
    if not leave: raise HTTPException(404, "Leave request not found.")
    ctx.db.add(LeaveSubstitution(organization_id=ctx.org_id, leave_id=leave.id, **payload.model_dump()))
    ctx.db.commit(); return _row(ctx, leave)
