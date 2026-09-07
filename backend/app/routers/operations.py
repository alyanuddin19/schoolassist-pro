"""Daily academic operations owned by the vice principal/coordinator."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import OrgContext, get_org_context
from ..models import (SchoolClass, Section, Subject, TeacherAttendance, TimetableEntry, ExamRoom, ExamSchedule,
                      User, ROLE_COORDINATOR, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL)

router = APIRouter(prefix="/ops", tags=["operations"])
OPS = (ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR)

class AttendanceEntry(BaseModel):
    teacher_id: int
    status: str
    check_in: str | None = None
    check_out: str | None = None
class AttendanceSave(BaseModel):
    date: str
    entries: list[AttendanceEntry]
class TimetableCreate(BaseModel):
    class_id: int; section_id: int | None = None; subject_id: int; teacher_id: int | None = None
    day: str; start_time: str; end_time: str
class RoomCreate(BaseModel):
    name: str
    capacity: int
class ApprovalInput(BaseModel):
    comment: str | None = None

def _timetable_row(ctx: OrgContext, item: TimetableEntry):
    classes = {x.id: x.name for x in ctx.db.query(SchoolClass).filter(SchoolClass.organization_id == ctx.org_id)}
    sections = {x.id: x.name for x in ctx.db.query(Section).filter(Section.organization_id == ctx.org_id)}
    subjects = {x.id: x.name for x in ctx.db.query(Subject).filter(Subject.organization_id == ctx.org_id)}
    user = ctx.db.get(User, item.teacher_id) if item.teacher_id else None
    return {"id": item.id, "class_id": item.class_id, "class": classes.get(item.class_id, ""),
      "section_id": item.section_id, "section": sections.get(item.section_id) if item.section_id else None,
      "subject_id": item.subject_id, "subject": subjects.get(item.subject_id, ""),
      "teacher_id": item.teacher_id, "teacher": user.full_name if user else None,
      "day": item.day, "start_time": item.start_time, "end_time": item.end_time}

@router.get("/attendance/teachers")
def teacher_attendance(date: str | None = None, month: str | None = None, ctx: OrgContext = Depends(get_org_context)):
    query = ctx.db.query(TeacherAttendance).filter(TeacherAttendance.organization_id == ctx.org_id)
    if date: query = query.filter(TeacherAttendance.date == date)
    if month: query = query.filter(TeacherAttendance.date.startswith(month))
    return [{"id": x.id, "teacher_id": x.teacher_id, "teacher": (ctx.db.get(User, x.teacher_id).full_name if ctx.db.get(User, x.teacher_id) else ""), "date": x.date, "status": x.status, "check_in": x.check_in, "check_out": x.check_out} for x in query.all()]

@router.post("/attendance/teachers")
def save_teacher_attendance(payload: AttendanceSave, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in OPS: raise HTTPException(403, "Only VP/coordinator can manage attendance exceptions.")
    for entry in payload.entries:
        row = ctx.db.query(TeacherAttendance).filter(TeacherAttendance.organization_id == ctx.org_id, TeacherAttendance.teacher_id == entry.teacher_id, TeacherAttendance.date == payload.date).first()
        if row is None:
            row = TeacherAttendance(organization_id=ctx.org_id, teacher_id=entry.teacher_id, date=payload.date, marked_by_id=ctx.user.id); ctx.db.add(row)
        row.status, row.check_in, row.check_out = entry.status, entry.check_in, entry.check_out
    ctx.db.commit(); return {"status": "saved"}

@router.get("/attendance/teachers/summary")
def teacher_summary(date: str, ctx: OrgContext = Depends(get_org_context)):
    rows = ctx.db.query(TeacherAttendance).filter(TeacherAttendance.organization_id == ctx.org_id, TeacherAttendance.date == date).all()
    counts = {x: sum(1 for row in rows if row.status == x) for x in ("present", "absent", "leave", "late")}
    return {"date": date, **counts, "marked": len(rows), "total_teachers": len(rows), "percent": round(counts["present"] * 100 / len(rows), 1) if rows else 0}

@router.get("/timetable")
def list_timetable(class_id: int | None = None, section_id: int | None = None, teacher_id: int | None = None, ctx: OrgContext = Depends(get_org_context)):
    q = ctx.db.query(TimetableEntry).filter(TimetableEntry.organization_id == ctx.org_id)
    if class_id: q = q.filter(TimetableEntry.class_id == class_id)
    if section_id: q = q.filter(TimetableEntry.section_id == section_id)
    if teacher_id: q = q.filter(TimetableEntry.teacher_id == teacher_id)
    return [_timetable_row(ctx, x) for x in q.order_by(TimetableEntry.day, TimetableEntry.start_time).all()]

@router.post("/timetable")
def create_timetable(payload: TimetableCreate, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in OPS: raise HTTPException(403, "Only VP/coordinator can create the timetable.")
    if payload.teacher_id:
        conflict = ctx.db.query(TimetableEntry).filter(TimetableEntry.organization_id == ctx.org_id, TimetableEntry.teacher_id == payload.teacher_id, TimetableEntry.day == payload.day, TimetableEntry.start_time < payload.end_time, TimetableEntry.end_time > payload.start_time).first()
        if conflict: raise HTTPException(409, "Teacher is already assigned during this period.")
    item = TimetableEntry(organization_id=ctx.org_id, **payload.model_dump()); ctx.db.add(item); ctx.db.commit(); ctx.db.refresh(item)
    return _timetable_row(ctx, item)

@router.delete("/timetable/{entry_id}")
def delete_timetable(entry_id: int, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in OPS: raise HTTPException(403, "Only VP/coordinator can edit the timetable.")
    row = ctx.db.query(TimetableEntry).filter(TimetableEntry.id == entry_id, TimetableEntry.organization_id == ctx.org_id).first()
    if not row: raise HTTPException(404, "Timetable entry not found.")
    ctx.db.delete(row); ctx.db.commit(); return {"status": "deleted"}

@router.post("/timetable/{class_id}/submit")
def submit_timetable(class_id: int, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in OPS: raise HTTPException(403, "Only VP/coordinator can submit a timetable.")
    ctx.db.query(TimetableEntry).filter(TimetableEntry.organization_id == ctx.org_id, TimetableEntry.class_id == class_id).update({"approval_status": "pending_principal_approval"})
    ctx.db.commit(); return {"status": "pending_principal_approval"}

@router.post("/timetable/{class_id}/approve")
def approve_timetable(class_id: int, payload: ApprovalInput, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role != "principal": raise HTTPException(403, "Only the principal can approve a timetable.")
    ctx.db.query(TimetableEntry).filter(TimetableEntry.organization_id == ctx.org_id, TimetableEntry.class_id == class_id).update({"approval_status": "approved", "approval_comment": payload.comment})
    ctx.db.commit(); return {"status": "approved", "comment": payload.comment}

@router.post("/timetable/{class_id}/return")
def return_timetable(class_id: int, payload: ApprovalInput, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role != "principal": raise HTTPException(403, "Only the principal can return a timetable.")
    ctx.db.query(TimetableEntry).filter(TimetableEntry.organization_id == ctx.org_id, TimetableEntry.class_id == class_id).update({"approval_status": "returned", "approval_comment": payload.comment})
    ctx.db.commit(); return {"status": "returned", "comment": payload.comment}

@router.get("/exams")
def list_exams(class_id: int | None = None, term: str | None = None, ctx: OrgContext = Depends(get_org_context)):
    q = ctx.db.query(ExamSchedule).filter(ExamSchedule.organization_id == ctx.org_id)
    if class_id: q = q.filter(ExamSchedule.class_id == class_id)
    if term: q = q.filter(ExamSchedule.term == term)
    classes = {x.id: x.name for x in ctx.db.query(SchoolClass).filter(SchoolClass.organization_id == ctx.org_id)}
    subjects = {x.id: x.name for x in ctx.db.query(Subject).filter(Subject.organization_id == ctx.org_id)}
    return [{"id": x.id, "term": x.term, "class_id": x.class_id, "class": classes.get(x.class_id, ""), "subject_id": x.subject_id, "subject": subjects.get(x.subject_id, ""), "date": x.date, "day": x.date, "start_time": x.start_time, "end_time": x.end_time} for x in q.order_by(ExamSchedule.date).all()]

@router.get("/exams/rooms")
def list_exam_rooms(ctx: OrgContext = Depends(get_org_context)):
    return [{"id": x.id, "name": x.name, "capacity": x.capacity} for x in ctx.db.query(ExamRoom).filter(ExamRoom.organization_id == ctx.org_id).order_by(ExamRoom.name).all()]

@router.post("/exams/rooms")
def create_exam_room(payload: RoomCreate, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role != "org_admin": raise HTTPException(403, "Only the admin can create exam rooms.")
    if payload.capacity < 1: raise HTTPException(400, "Room capacity must be at least 1.")
    row = ExamRoom(organization_id=ctx.org_id, name=payload.name.strip(), capacity=payload.capacity)
    ctx.db.add(row); ctx.db.commit(); ctx.db.refresh(row)
    return {"id": row.id, "name": row.name, "capacity": row.capacity}
