"""Reports: student performance, subject reports, weak students, final term reports."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import OrgContext, get_org_context
from ..models import (
    ROLE_COORDINATOR,
    ROLE_ORG_ADMIN,
    ROLE_PRINCIPAL,
    ROLE_VICE_PRINCIPAL,
    Report,
    SchoolClass,
)
from ..schemas import FinalTermReportRequest
from ..services import analytics
from ..services.access import ensure_teacher_can_access, visible_class_ids_for_teacher

router = APIRouter(prefix="/reports", tags=["reports"])


def _serialize_report(db, ctx: OrgContext, report: Report) -> dict:
    school_class = db.get(SchoolClass, report.class_id) if report.class_id else None
    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "class_id": report.class_id,
        "class": school_class.name if school_class else None,
        "student_id": report.student_id,
        "subject_id": report.subject_id,
        "academic_year": report.academic_year,
        "content": report.content,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/students/{student_id}")
def student_report(student_id: int, ctx: OrgContext = Depends(get_org_context)):
    performance = analytics.student_performance(ctx.db, ctx.org_id, student_id)
    if not performance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return performance


@router.get("/subject")
def subject_report(
    class_id: int = Query(...),
    subject_id: int = Query(...),
    section_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    ensure_teacher_can_access(ctx.db, ctx, class_id, subject_id)
    return analytics.subject_performance(ctx.db, ctx.org_id, class_id, subject_id, section_id)


@router.get("/class-performance")
def class_performance(
    class_id: int = Query(...),
    section_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    if ctx.member.role == "teacher" and ctx.is_school:
        allowed = visible_class_ids_for_teacher(ctx.db, ctx) or []
        if class_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this class.",
            )
    return analytics.class_report(ctx.db, ctx.org_id, class_id, section_id)


@router.get("/weak-students")
def weak_students(
    class_id: int = Query(...),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    threshold: float = Query(default=40.0),
    ctx: OrgContext = Depends(get_org_context),
):
    if subject_id:
        ensure_teacher_can_access(ctx.db, ctx, class_id, subject_id)
    return analytics.weak_students(
        ctx.db,
        ctx.org_id,
        class_id,
        subject_id=subject_id,
        section_id=section_id,
        threshold_percent=threshold,
    )


@router.post("/final-term")
def create_final_term_report(
    payload: FinalTermReportRequest, ctx: OrgContext = Depends(get_org_context)
):
    """Coordinator / principal / school owner action: consolidated final term report."""
    allowed = ctx.role in (ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR)
    if not allowed and not ctx.is_individual:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the coordinator, principal or school owner can create final term reports.",
        )
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == payload.class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")

    report = analytics.build_final_term_report(
        ctx.db,
        ctx.org_id,
        payload.class_id,
        section_id=payload.section_id,
        generated_by_id=ctx.user.id,
        title=payload.title,
        academic_year=payload.academic_year,
    )
    return _serialize_report(ctx.db, ctx, report)


@router.get("")
def list_reports(
    report_type: str | None = Query(default=None),
    class_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    query = ctx.db.query(Report).filter(Report.organization_id == ctx.org_id)
    if report_type:
        query = query.filter(Report.report_type == report_type)
    if class_id:
        query = query.filter(Report.class_id == class_id)
    reports = query.order_by(Report.created_at.desc()).limit(100).all()
    return [_serialize_report(ctx.db, ctx, report) for report in reports]


@router.get("/admin-summary")
def admin_summary(ctx: OrgContext = Depends(get_org_context)):
    """One-shot school summary for the admin Reports page: enrollment,
    class-wise students, teacher list, attendance summary, exam schedule
    and student distribution."""
    from datetime import date as date_type, timedelta

    from ..models import (
        ExamSchedule,
        OrganizationMember,
        Section,
        Student,
        StudentAttendance,
        Subject,
        Teacher,
        TeacherSubject,
        User,
    )

    db = ctx.db
    org_id = ctx.org_id
    classes = (
        db.query(SchoolClass).filter(SchoolClass.organization_id == org_id).order_by(SchoolClass.id).all()
    )
    sections = db.query(Section).filter(Section.organization_id == org_id).all()
    section_names = {s.id: s.name for s in sections}
    students = db.query(Student).filter(Student.organization_id == org_id).all()
    active_students = [s for s in students if s.is_active]

    class_wise = []
    for school_class in classes:
        in_class = [s for s in active_students if s.class_id == school_class.id]
        by_section: dict[str, int] = {}
        for s in in_class:
            key = section_names.get(s.section_id, "Unassigned") if s.section_id else "Unassigned"
            by_section[key] = by_section.get(key, 0) + 1
        class_wise.append(
            {
                "class_id": school_class.id,
                "class": school_class.name,
                "students": len(in_class),
                "sections": by_section,
            }
        )

    members = (
        db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == org_id)
        .order_by(User.full_name.asc())
        .all()
    )
    profiles = {t.user_id: t for t in db.query(Teacher).filter(Teacher.organization_id == org_id).all()}
    subject_rows = db.query(TeacherSubject).filter(TeacherSubject.organization_id == org_id).all()
    subjects_by_teacher: dict[int, list[int]] = {}
    for row in subject_rows:
        subjects_by_teacher.setdefault(row.teacher_id, []).append(row.subject_id)
    subject_names = {
        s.id: s.name for s in db.query(Subject).filter(Subject.organization_id == org_id).all()
    }
    teachers = [
        {
            "name": user.full_name,
            "role": member.role,
            "designation": profiles[user.id].designation if user.id in profiles else None,
            "department": profiles[user.id].department if user.id in profiles else None,
            "subjects": [subject_names.get(sid, "") for sid in subjects_by_teacher.get(user.id, [])],
            "is_active": member.is_active,
        }
        for member, user in members
        if member.role != ROLE_ORG_ADMIN
    ]

    today = date_type.today()
    week_start = (today - timedelta(days=6)).isoformat()
    attendance = (
        db.query(StudentAttendance)
        .filter(
            StudentAttendance.organization_id == org_id,
            StudentAttendance.date >= week_start,
            StudentAttendance.date <= today.isoformat(),
        )
        .all()
    )
    per_day: dict[str, dict[str, int]] = {}
    for row in attendance:
        bucket = per_day.setdefault(row.date, {"present": 0, "absent": 0, "leave": 0, "late": 0})
        bucket[row.status] = bucket.get(row.status, 0) + 1
    attendance_summary = [
        {"date": day, **counts, "marked": sum(counts.values())}
        for day, counts in sorted(per_day.items())
    ]

    exams = (
        db.query(ExamSchedule)
        .filter(ExamSchedule.organization_id == org_id, ExamSchedule.date >= today.isoformat())
        .order_by(ExamSchedule.date.asc())
        .all()
    )
    class_names = {c.id: c.name for c in classes}
    return {
        "enrollment": {
            "total": len(students),
            "active": len(active_students),
            "inactive": len(students) - len(active_students),
        },
        "class_wise": class_wise,
        "teachers": teachers,
        "attendance": attendance_summary,
        "exam_schedule": [
            {
                "term": e.term,
                "class": class_names.get(e.class_id, ""),
                "subject": subject_names.get(e.subject_id, ""),
                "date": e.date,
                "start_time": e.start_time,
                "end_time": e.end_time,
            }
            for e in exams
        ],
        "distribution": [
            {
                "class": row["class"],
                "section": section_name,
                "students": count,
            }
            for row in class_wise
            for section_name, count in sorted(row["sections"].items())
        ],
    }


@router.get("/{report_id}")
def get_report(report_id: int, ctx: OrgContext = Depends(get_org_context)):
    report = (
        ctx.db.query(Report)
        .filter(Report.id == report_id, Report.organization_id == ctx.org_id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return _serialize_report(ctx.db, ctx, report)
