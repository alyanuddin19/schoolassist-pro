"""Dashboard data endpoints for teacher, school admin and coordinator views."""

from collections import Counter

from fastapi import APIRouter, Depends, Query

from ..deps import OrgContext, get_org_context, require_roles
from ..models import (
    ROLE_COORDINATOR,
    ROLE_ORG_ADMIN,
    ROLE_PRINCIPAL,
    ROLE_TEACHER,
    ROLE_VICE_PRINCIPAL,
    Marksheet,
    Report,
    SchoolClass,
    Section,
    Student,
    Subject,
    TeacherSubjectAssignment,
    Test,
    Worksheet,
    ClassSubject,
    ExamRoom,
    ExamSchedule,
    Announcement,
    TeacherAttendance,
    TeacherLeave,
    TimetableEntry,
    OrganizationMember,
    User,
    Teacher,
    SchoolSetting,
)
from ..services import access, analytics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/principal")
def principal_dashboard(
    ctx: OrgContext = Depends(require_roles(ROLE_PRINCIPAL))
):
    """Monitoring-only data for the principal's approval desk."""
    from collections import Counter
    from datetime import date as date_type

    db, org_id = ctx.db, ctx.org_id
    today = date_type.today().isoformat()
    students = db.query(Student).filter(Student.organization_id == org_id, Student.is_active.is_(True)).count()
    classes = db.query(SchoolClass).filter(SchoolClass.organization_id == org_id).all()
    sections = db.query(Section).filter(Section.organization_id == org_id).count()
    subjects = db.query(Subject).filter(Subject.organization_id == org_id).count()
    teachers = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_id, OrganizationMember.is_active.is_(True), OrganizationMember.role.in_([ROLE_TEACHER, ROLE_COORDINATOR, ROLE_VICE_PRINCIPAL])).count()
    attendance = db.query(TeacherAttendance).filter(TeacherAttendance.organization_id == org_id, TeacherAttendance.date == today).all()
    counts = Counter(x.status for x in attendance)
    staff = {u.id: u.full_name for u in db.query(User).join(OrganizationMember, OrganizationMember.user_id == User.id).filter(OrganizationMember.organization_id == org_id).all()}
    alerts = [{"teacher": staff.get(x.teacher_id, "Staff member"), "status": x.status} for x in attendance if x.status in ("absent", "late", "leave")]
    assignments = db.query(TeacherSubjectAssignment).filter(TeacherSubjectAssignment.organization_id == org_id).all()
    assigned = {(x.class_id, x.subject_id) for x in assignments}
    required = {(x.class_id, x.subject_id) for x in db.query(ClassSubject).filter(ClassSubject.organization_id == org_id).all()}
    unassigned = required - assigned
    class_names = {x.id: x.name for x in classes}; subject_names = {x.id: x.name for x in db.query(Subject).filter(Subject.organization_id == org_id).all()}
    timetable = db.query(TimetableEntry).filter(TimetableEntry.organization_id == org_id).all()
    time_keys = Counter((x.teacher_id, x.day, x.start_time) for x in timetable if x.teacher_id)
    conflicts = sum(1 for n in time_keys.values() if n > 1)
    leaves = db.query(TeacherLeave).filter(TeacherLeave.organization_id == org_id, TeacherLeave.status == "pending_principal_approval").order_by(TeacherLeave.created_at.desc()).all()
    approvals = [{"type": "Teacher leave", "title": f"Leave request — {staff.get(x.teacher_id, 'Teacher')}", "description": x.reason, "submitted_by": staff.get(x.requested_by_id, "Teacher"), "status": "Pending", "date": x.created_at.isoformat() if x.created_at else None, "route": "/leaves"} for x in leaves]
    exams = db.query(ExamSchedule).filter(ExamSchedule.organization_id == org_id, ExamSchedule.date >= today).order_by(ExamSchedule.date).all()
    by_term = {}
    for exam in exams:
        info = by_term.setdefault(exam.term, {"term": exam.term, "start_date": exam.date, "classes": set(), "papers": 0})
        info["start_date"] = min(info["start_date"], exam.date); info["classes"].add(exam.class_id); info["papers"] += 1
    rooms = db.query(ExamRoom).filter(ExamRoom.organization_id == org_id).count()
    announcements = db.query(Announcement).filter(Announcement.organization_id == org_id).order_by(Announcement.published_at.desc()).limit(5).all()
    return {"students": students, "teachers": teachers, "classes": len(classes), "sections": sections, "subjects": subjects, "exam_rooms": rooms,
        "attendance_today": {"present": counts["present"], "late": counts["late"], "absent": counts["absent"], "on_leave": counts["leave"], "marked": len(attendance), "alerts": alerts[:5]},
        "pending_approvals": approvals, "upcoming_exams": [{**x, "classes": len(x["classes"]), "timetable_status": "Complete" if x["papers"] else "Pending", "rooms_status": "Configured" if rooms else "Not configured", "seating_status": "Review required"} for x in by_term.values()],
        "academic_status": {"teacher_allocation_complete": len({a.class_id for a in assignments}), "total_classes": len(classes), "timetable_completion_percentage": round(min(100, (len(timetable) / max(len(required) * 5, 1)) * 100)), "unassigned_subjects": len(unassigned), "timetable_conflicts": conflicts, "alerts": [f"{class_names.get(c, 'Class')} — {subject_names.get(s, 'subject')} has no assigned teacher." for c, s in list(unassigned)[:3]]},
        "recent_announcements": [{"id": x.id, "title": x.title, "audience": x.audience, "message": x.message, "published_at": x.published_at.isoformat() if x.published_at else None} for x in announcements]}


@router.get("/principal/school-overview")
def principal_school_overview(ctx: OrgContext = Depends(require_roles(ROLE_PRINCIPAL))):
    """Read-only school structure and capacity view for the principal."""
    db, org_id = ctx.db, ctx.org_id
    classes = db.query(SchoolClass).filter(SchoolClass.organization_id == org_id).order_by(SchoolClass.grade_level, SchoolClass.name).all()
    sections = db.query(Section).filter(Section.organization_id == org_id).all()
    students = db.query(Student).filter(Student.organization_id == org_id, Student.is_active.is_(True)).all()
    subjects = db.query(Subject).filter(Subject.organization_id == org_id).all()
    teachers = db.query(Teacher).filter(Teacher.organization_id == org_id, Teacher.status == "active").all()
    users = {x.id: x.full_name for x in db.query(User).all()}
    sections_by_class = {}
    for item in sections: sections_by_class.setdefault(item.class_id, []).append(item)
    students_by_class = Counter(x.class_id for x in students)
    subject_count = Counter(x.class_id for x in db.query(ClassSubject).filter(ClassSubject.organization_id == org_id).all())
    assignment_pairs = {(x.class_id, x.subject_id) for x in db.query(TeacherSubjectAssignment).filter(TeacherSubjectAssignment.organization_id == org_id).all()}
    required_pairs = {(x.class_id, x.subject_id) for x in db.query(ClassSubject).filter(ClassSubject.organization_id == org_id).all()}
    def level_for(grade):
        if grade is None: return "Unspecified"
        if grade <= 0: return "Pre-Primary"
        if grade <= 5: return "Primary"
        if grade <= 8: return "Middle"
        if grade <= 10: return "Secondary"
        return "Higher Secondary"
    level_data = {}
    for item in classes:
        name = level_for(item.grade_level)
        bucket = level_data.setdefault(name, {"level": name, "classes": 0, "sections": 0, "students": 0})
        bucket["classes"] += 1; bucket["sections"] += len(sections_by_class.get(item.id, [])); bucket["students"] += students_by_class[item.id]
    class_rows, capacity_alerts, no_teachers = [], [], []
    for item in classes:
        enrolled, capacity = students_by_class[item.id], item.capacity
        class_sections = sections_by_class.get(item.id, [])
        lead = next((x for x in class_sections if x.class_teacher_id), None)
        label, usage = "Not Set", None
        if capacity:
            usage = round(enrolled * 100 / capacity)
            label = "Full" if enrolled >= capacity else "Almost Full" if usage >= 85 else "Available"
            if label != "Available": capacity_alerts.append(f"{item.name} is {enrolled} / {capacity} students — {label}")
        if not lead: no_teachers.extend([f"{item.name}{' ' + x.name if x.name else ''} has no class teacher." for x in class_sections] or [f"{item.name} has no class teacher."])
        class_rows.append({"id": item.id, "name": item.name, "academic_level": level_for(item.grade_level), "sections": len(class_sections), "students": enrolled, "class_teacher": users.get(lead.class_teacher_id) if lead else None, "subjects": subject_count[item.id], "capacity": capacity, "usage": usage, "capacity_status": label})
    department_counts = Counter((x.department or "Unassigned") for x in teachers)
    assigned_teacher_ids = {x.teacher_id for x in db.query(TeacherSubjectAssignment).filter(TeacherSubjectAssignment.organization_id == org_id).all()}
    setting = db.get(SchoolSetting, org_id)
    rooms = db.query(ExamRoom).filter(ExamRoom.organization_id == org_id).all()
    upcoming = db.query(ExamSchedule).filter(ExamSchedule.organization_id == org_id).order_by(ExamSchedule.date.desc()).first()
    members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_id, OrganizationMember.is_active.is_(True)).all()
    principal = next((users.get(x.user_id) for x in members if x.role == ROLE_PRINCIPAL), None)
    vp = next((users.get(x.user_id) for x in members if x.role == ROLE_VICE_PRINCIPAL), None)
    alerts = [f"{next((c.name for c in classes if c.id == cid), 'Class')} {next((s.name for s in subjects if s.id == sid), 'subject')} has no assigned teacher." for cid, sid in list(required_pairs - assignment_pairs)[:4]] + no_teachers[:4]
    return {"summary": {"students": len(students), "teachers": len(teachers), "classes": len(classes), "sections": len(sections), "subjects": len(subjects), "departments": len([x for x in department_counts if x != "Unassigned"])}, "academic_levels": list(level_data.values()), "class_overview": class_rows, "capacity": {"total": sum(x.capacity or 0 for x in classes), "enrolled": len(students), "available": sum(max((x.capacity or 0) - students_by_class[x.id], 0) for x in classes if x.capacity), "full_classes": sum(1 for x in class_rows if x["capacity_status"] == "Full"), "near_capacity": sum(1 for x in class_rows if x["capacity_status"] == "Almost Full"), "alerts": capacity_alerts}, "teacher_distribution": [{"name": k, "teachers": v} for k, v in department_counts.items()], "teachers_without_assignment": sum(1 for x in teachers if x.user_id not in assigned_teacher_ids), "student_distribution": [{"level": x["level"], "students": x["students"]} for x in level_data.values()], "academic_setup": {"subject_setup_complete": sum(1 for x in classes if subject_count[x.id]), "teacher_allocation_complete": len({x[0] for x in assignment_pairs}), "total_classes": len(classes), "unassigned_subjects": len(required_pairs - assignment_pairs), "sections_without_teacher": sum(1 for x in sections if not x.class_teacher_id), "alerts": alerts}, "exam_infrastructure": {"rooms": len(rooms), "capacity": sum(x.capacity for x in rooms), "upcoming_term": upcoming.term if upcoming else None, "seating_status": "Not generated"}, "school_info": {"name": ctx.organization.name, "academic_year": setting.academic_year if setting else None, "principal": principal, "vice_principal": vp, "school_type": ctx.organization.org_type, "departments": len([x for x in department_counts if x != "Unassigned"])}}


@router.get("/principal/teachers")
def principal_teachers(ctx: OrgContext = Depends(require_roles(ROLE_PRINCIPAL))):
    """Read-only staff profiles, academic allocation and operational summaries."""
    from datetime import date as date_type

    db, org_id = ctx.db, ctx.org_id
    today = date_type.today().isoformat()
    profiles = db.query(Teacher).filter(Teacher.organization_id == org_id).all()
    users = {x.id: x for x in db.query(User).all()}
    classes = {x.id: x.name for x in db.query(SchoolClass).filter(SchoolClass.organization_id == org_id)}
    sections = {x.id: x.name for x in db.query(Section).filter(Section.organization_id == org_id)}
    subjects = {x.id: x.name for x in db.query(Subject).filter(Subject.organization_id == org_id)}
    assignments_by_teacher = {}
    for row in db.query(TeacherSubjectAssignment).filter(TeacherSubjectAssignment.organization_id == org_id):
        assignments_by_teacher.setdefault(row.teacher_id, []).append(row)
    timetable_by_teacher = Counter(x.teacher_id for x in db.query(TimetableEntry).filter(TimetableEntry.organization_id == org_id, TimetableEntry.teacher_id.isnot(None)).all())
    attendance_by_teacher = {}
    for row in db.query(TeacherAttendance).filter(TeacherAttendance.organization_id == org_id).all():
        attendance_by_teacher.setdefault(row.teacher_id, []).append(row)
    active_leave = {x.teacher_id for x in db.query(TeacherLeave).filter(TeacherLeave.organization_id == org_id, TeacherLeave.status == "approved", TeacherLeave.start_date <= today, TeacherLeave.end_date >= today).all()}
    leave_count = Counter(x.teacher_id for x in db.query(TeacherLeave).filter(TeacherLeave.organization_id == org_id).all())
    rows = []
    for profile in profiles:
        user = users.get(profile.user_id)
        if user is None: continue
        allocations = assignments_by_teacher.get(profile.user_id, [])
        attendance = attendance_by_teacher.get(profile.user_id, [])
        present = sum(1 for x in attendance if x.status in ("present", "late"))
        percentage = round(present * 100 / len(attendance)) if attendance else None
        subject_names = sorted({subjects.get(x.subject_id, "") for x in allocations if subjects.get(x.subject_id)})
        class_names = sorted({f"{classes.get(x.class_id, '')}{' · ' + sections.get(x.section_id, '') if x.section_id else ''}" for x in allocations})
        rows.append({"id": profile.user_id, "name": user.full_name, "employee_id": profile.employee_id, "email": user.email, "phone": user.phone, "qualification": profile.qualification, "department": profile.department or "Unassigned", "designation": profile.designation, "subjects": subject_names, "classes": class_names, "academic_year": next((x.academic_year for x in allocations if x.academic_year), None), "weekly_workload": timetable_by_teacher[profile.user_id], "attendance_percentage": percentage, "attendance_marked": len(attendance), "leave_count": leave_count[profile.user_id], "status": "On Leave" if profile.user_id in active_leave else profile.status.title(), "assignment_status": "Assigned" if allocations else "Unassigned"})
    return {"summary": {"total": len(rows), "active": sum(1 for x in rows if x["status"] == "Active"), "on_leave": sum(1 for x in rows if x["status"] == "On Leave"), "unassigned": sum(1 for x in rows if x["assignment_status"] == "Unassigned")}, "teachers": rows, "departments": sorted({x["department"] for x in rows}), "subjects": sorted(subjects.values()), "classes": sorted(classes.values())}


@router.get("/principal/academic-monitoring")
def principal_academic_monitoring(ctx: OrgContext = Depends(require_roles(ROLE_PRINCIPAL))):
    """Read-only allocation and timetable health for the principal."""
    db, org_id = ctx.db, ctx.org_id
    classes = db.query(SchoolClass).filter(SchoolClass.organization_id == org_id).all(); sections = db.query(Section).filter(Section.organization_id == org_id).all()
    subjects = {x.id: x.name for x in db.query(Subject).filter(Subject.organization_id == org_id)}; users = {x.id: x.full_name for x in db.query(User).all()}
    required = list(db.query(ClassSubject).filter(ClassSubject.organization_id == org_id)); assignments = list(db.query(TeacherSubjectAssignment).filter(TeacherSubjectAssignment.organization_id == org_id)); timetable = list(db.query(TimetableEntry).filter(TimetableEntry.organization_id == org_id))
    by_class_required = Counter(x.class_id for x in required); assigned_pairs = {(x.class_id, x.subject_id) for x in assignments}; by_class_assigned = Counter(x.class_id for x in assignments)
    class_names = {x.id: x.name for x in classes}; sec_by_class = {}; 
    for x in sections: sec_by_class.setdefault(x.class_id, []).append(x)
    teacher_slots = Counter(x.teacher_id for x in timetable if x.teacher_id); conflict_keys = Counter((x.teacher_id, x.day, x.start_time) for x in timetable if x.teacher_id); conflict_teachers = {k[0] for k,v in conflict_keys.items() if v > 1}
    unassigned = [{"class": class_names.get(x.class_id, ""), "class_id": x.class_id, "subject": subjects.get(x.subject_id, ""), "issue": "No teacher assigned", "status": "Needs Attention"} for x in required if (x.class_id, x.subject_id) not in assigned_pairs]
    class_rows = []
    for c in classes:
        total, allocated = by_class_required[c.id], len({x.subject_id for x in assignments if x.class_id == c.id})
        periods = sum(1 for x in timetable if x.class_id == c.id); expected = max(total * 5, 1); pct = round(min(100, periods * 100 / expected)); missing = max(0, expected - periods)
        status = "Complete" if allocated == total and pct == 100 else "Incomplete" if allocated == 0 else "Needs Attention"
        class_rows.append({"id": c.id, "name": c.name, "level": "Primary" if (c.grade_level or 0) <= 5 else "Secondary", "sections": len(sec_by_class.get(c.id, [])), "total_subjects": total, "assigned_subjects": allocated, "allocation_percent": round(allocated * 100 / total) if total else 0, "timetable_percent": pct, "missing_periods": missing, "status": status, "details": [{"subject": subjects.get(x.subject_id, ""), "teacher": users.get(x.teacher_id, "Not assigned")} for x in assignments if x.class_id == c.id]})
    profiles = {x.user_id: x for x in db.query(Teacher).filter(Teacher.organization_id == org_id)}; workload = []
    for teacher_id, profile in profiles.items():
        periods = teacher_slots[teacher_id]; state = "Overloaded" if periods > 32 else "Underutilized" if periods and periods < 12 else "Normal"
        a = [x for x in assignments if x.teacher_id == teacher_id]
        workload.append({"name": users.get(teacher_id, ""), "employee_id": profile.employee_id, "department": profile.department or "Unassigned", "classes": len({x.class_id for x in a}), "subjects": len({x.subject_id for x in a}), "periods": periods, "status": state})
    alerts = [{"title": f"{x['class']} — {x['subject']}", "description": "No teacher assigned.", "severity": "High"} for x in unassigned[:6]] + [{"title": users.get(x, "Teacher"), "description": "Timetable conflict detected.", "severity": "High"} for x in conflict_teachers] + [{"title": x["name"], "description": "Teacher workload is high.", "severity": "Medium"} for x in workload if x["status"] == "Overloaded"]
    complete_alloc = sum(1 for x in class_rows if x["total_subjects"] and x["assigned_subjects"] == x["total_subjects"]); complete_time = sum(1 for x in class_rows if x["timetable_percent"] == 100)
    return {"summary": {"total_classes": len(classes), "complete_allocation": complete_alloc, "total_subjects": len(required), "assigned_subjects": len(required)-len(unassigned), "unassigned_subjects": len(unassigned), "timetable_percent": round(min(100, len(timetable)*100/max(len(required)*5,1))), "conflicts": len(conflict_teachers), "needs_attention": sum(1 for x in class_rows if x["status"] != "Complete")}, "classes": class_rows, "unassigned": unassigned, "timetable": {"scheduled": len(timetable), "missing": sum(x["missing_periods"] for x in class_rows), "conflicts": len(conflict_teachers), "incomplete": sum(1 for x in class_rows if x["timetable_percent"] < 100), "overload": sum(1 for x in workload if x["status"] == "Overloaded")}, "workload": workload, "setup": {"subjects": sum(1 for x in class_rows if x["total_subjects"]), "allocation": complete_alloc, "timetable": complete_time, "class_teachers": sum(1 for x in sections if x.class_teacher_id), "sections": len(sections)}, "alerts": alerts}


def _scoped_class_ids(ctx: OrgContext) -> list[int] | None:
    return access.visible_class_ids_for_teacher(ctx.db, ctx)


@router.get("/teacher")
def teacher_dashboard(ctx: OrgContext = Depends(get_org_context)):
    db = ctx.db
    is_teacher_only = ctx.member.role == ROLE_TEACHER and ctx.is_school

    assignments_query = db.query(TeacherSubjectAssignment).filter(
        TeacherSubjectAssignment.organization_id == ctx.org_id
    )
    assignments = assignments_query.all()
    my_assignments = [a for a in assignments if a.teacher_id == ctx.user.id]

    class_ids = sorted({a.class_id for a in my_assignments}) if is_teacher_only else None
    scope_class_ids = class_ids if class_ids is not None else [c.id for c in db.query(SchoolClass).filter(SchoolClass.organization_id == ctx.org_id).all()]

    class_names = {c.id: c.name for c in db.query(SchoolClass).filter(SchoolClass.id.in_(scope_class_ids or [0])).all()} if scope_class_ids else {}
    subject_names = {s.id: s.name for s in db.query(Subject).filter(Subject.organization_id == ctx.org_id).all()}

    def class_name(class_id):
        return class_names.get(class_id, "")

    def subject_name(subject_id):
        return subject_names.get(subject_id, "")

    students_count = (
        db.query(Student)
        .filter(
            Student.organization_id == ctx.org_id,
            Student.class_id.in_(scope_class_ids or [0]),
            Student.is_active.is_(True),
        )
        .count()
        if scope_class_ids
        else 0
    )

    worksheet_query = db.query(Worksheet).filter(Worksheet.organization_id == ctx.org_id)
    test_query = db.query(Test).filter(Test.organization_id == ctx.org_id)
    marksheet_query = db.query(Marksheet).filter(Marksheet.organization_id == ctx.org_id)
    if is_teacher_only:
        worksheet_query = worksheet_query.filter(Worksheet.created_by_id == ctx.user.id)
        test_query = test_query.filter(Test.created_by_id == ctx.user.id)
        marksheet_query = marksheet_query.filter(Marksheet.class_id.in_(scope_class_ids or [0]))

    recent_worksheets = worksheet_query.order_by(Worksheet.created_at.desc()).limit(5).all()
    recent_tests = test_query.order_by(Test.created_at.desc()).limit(5).all()
    recent_marksheets = marksheet_query.order_by(Marksheet.created_at.desc()).limit(5).all()

    return {
        "user": {"name": ctx.user.full_name, "role": ctx.role},
        "organization": {"name": ctx.organization.name, "type": ctx.organization.org_type},
        "stats": {
            "my_classes": len({a.class_id for a in my_assignments}) if my_assignments else len(scope_class_ids or []),
            "my_subjects": len({a.subject_id for a in my_assignments}) if my_assignments else len(subject_names),
            "my_students": students_count,
            "worksheets": worksheet_query.count(),
            "tests": test_query.count(),
            "marksheets": marksheet_query.count(),
        },
        "assignments": [
            {
                "id": a.id,
                "class": class_name(a.class_id),
                "subject": subject_name(a.subject_id),
                "academic_year": a.academic_year,
            }
            for a in (my_assignments if my_assignments else assignments)[:20]
        ],
        "recent_worksheets": [
            {
                "id": w.id,
                "title": w.title,
                "class": class_name(w.class_id),
                "subject": subject_name(w.subject_id),
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in recent_worksheets
        ],
        "recent_tests": [
            {
                "id": t.id,
                "title": t.title,
                "test_type": t.test_type,
                "class": class_name(t.class_id),
                "subject": subject_name(t.subject_id),
                "total_marks": t.total_marks,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent_tests
        ],
        "recent_marksheets": [
            {
                "id": m.id,
                "title": m.title,
                "class": class_name(m.class_id),
                "subject": subject_name(m.subject_id),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in recent_marksheets
        ],
    }


@router.get("/admin")
def admin_dashboard(
    ctx: OrgContext = Depends(
        require_roles(ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL)
    )
):
    from .organizations import org_overview

    overview = org_overview(ctx)
    db = ctx.db

    from datetime import date as date_type

    from ..models import (
        ExamSchedule,
        OrganizationMember,
        StudentAttendance,
        Subject,
        TeacherAttendance,
        User,
    )

    members = (
        db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(
            OrganizationMember.organization_id == ctx.org_id,
            OrganizationMember.is_active.is_(True),
        )
        .all()
    )
    role_counts: dict[str, int] = {}
    for member, _ in members:
        role_counts[member.role] = role_counts.get(member.role, 0) + 1

    today = date_type.today().isoformat()
    student_att = (
        db.query(StudentAttendance)
        .filter(StudentAttendance.organization_id == ctx.org_id, StudentAttendance.date == today)
        .all()
    )
    student_counts = {"present": 0, "absent": 0, "leave": 0, "late": 0}
    for row in student_att:
        student_counts[row.status] = student_counts.get(row.status, 0) + 1
    teacher_att = (
        db.query(TeacherAttendance)
        .filter(TeacherAttendance.organization_id == ctx.org_id, TeacherAttendance.date == today)
        .all()
    )
    teacher_counts = {"present": 0, "absent": 0, "leave": 0, "late": 0}
    teacher_ids = {m.user_id for m, _ in members if m.role == ROLE_TEACHER}
    teacher_marked = 0
    for row in teacher_att:
        # The register covers all staff; the dashboard KPI is teachers only.
        if row.teacher_id not in teacher_ids:
            continue
        teacher_marked += 1
        teacher_counts[row.status] = teacher_counts.get(row.status, 0) + 1

    class_names = {
        c.id: c.name
        for c in db.query(SchoolClass).filter(SchoolClass.organization_id == ctx.org_id).all()
    }
    subject_names = {
        s.id: s.name for s in db.query(Subject).filter(Subject.organization_id == ctx.org_id).all()
    }
    upcoming = (
        db.query(ExamSchedule)
        .filter(ExamSchedule.organization_id == ctx.org_id, ExamSchedule.date >= today)
        .order_by(ExamSchedule.date.asc(), ExamSchedule.start_time.asc())
        .limit(6)
        .all()
    )

    active_students = (
        db.query(Student)
        .filter(Student.organization_id == ctx.org_id, Student.is_active.is_(True))
        .count()
    )

    return {
        **overview,
        "role_counts": role_counts,
        "active_members": len(members),
        "headcount": {
            "students": active_students,
            "teachers": role_counts.get(ROLE_TEACHER, 0),
            "classes": overview["counts"]["classes"],
            "staff": sum(
                count for role, count in role_counts.items() if role != ROLE_TEACHER
            ),
        },
        "attendance_today": {
            "date": today,
            "students": {**student_counts, "marked": len(student_att)},
            "teachers": {**teacher_counts, "marked": teacher_marked},
        },
        "upcoming_exams": [
            {
                "id": e.id,
                "term": e.term,
                "class": class_names.get(e.class_id, ""),
                "subject": subject_names.get(e.subject_id, ""),
                "date": e.date,
                "start_time": e.start_time,
                "end_time": e.end_time,
            }
            for e in upcoming
        ],
    }


@router.get("/coordinator")
def coordinator_dashboard(
    class_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(
        require_roles(ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR)
    ),
):
    db = ctx.db
    classes = (
        db.query(SchoolClass)
        .filter(SchoolClass.organization_id == ctx.org_id)
        .order_by(SchoolClass.id.asc())
        .all()
    )

    selected_class = None
    if class_id:
        selected_class = next((c for c in classes if c.id == class_id), None)
    if selected_class is None and classes:
        selected_class = classes[0]

    class_perf = None
    weak = None
    if selected_class is not None:
        class_perf = analytics.class_report(db, ctx.org_id, selected_class.id)
        weak = analytics.weak_students(db, ctx.org_id, selected_class.id)

    final_reports = (
        db.query(Report)
        .filter(
            Report.organization_id == ctx.org_id,
            Report.report_type == "final_term",
        )
        .order_by(Report.created_at.desc())
        .limit(6)
        .all()
    )

    return {
        "classes": [
            {"id": c.id, "name": c.name, "grade_level": c.grade_level} for c in classes
        ],
        "selected_class": (
            {"id": selected_class.id, "name": selected_class.name} if selected_class else None
        ),
        "class_performance": class_perf,
        "weak_students": weak,
        "final_reports": [
            {
                "id": r.id,
                "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in final_reports
        ],
    }
