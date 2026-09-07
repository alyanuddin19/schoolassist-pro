"""Safe backend action handlers for the AI assistant (dashboard controller).

The chatbot never writes to the database directly. It selects one of these
registered, permission-checked handlers; every handler is org-scoped and
returns a structured, frontend-friendly display payload.
"""

import secrets

from fastapi import HTTPException, status

from ..deps import OrgContext
from ..models import (
    Marksheet,
    MarksheetEntry,
    ROLE_COORDINATOR,
    ROLE_ORG_ADMIN,
    ROLE_PRINCIPAL,
    ROLE_TEACHER,
    Student,
    TeacherInvite,
)
from ..schemas import QuestionCounts, TestGenerateRequest, WorksheetGenerateRequest
from . import access, analytics
from .content_service import create_test, create_worksheet

# ------------------------------------------------------------------
# Action registry
# ------------------------------------------------------------------


class ActionSpec:
    def __init__(self, name, description, params, handler=None, allowed_roles=None):
        self.name = name
        self.description = description
        self.params = params
        self.handler = handler
        self.allowed_roles = allowed_roles  # None => all roles


ACTION_REGISTRY: dict[str, ActionSpec] = {}


def action(name: str, description: str, params: str = "", allowed_roles: tuple | None = None):
    def decorator(func):
        ACTION_REGISTRY[name] = ActionSpec(
            name, description, params, handler=func, allowed_roles=allowed_roles
        )
        return func

    return decorator


def _resolve_class(ctx: OrgContext, params: dict):
    from ..models import SchoolClass

    class_id = params.get("class_id")
    school_class = None
    if class_id:
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            class_id = None
    if class_id:
        school_class = (
            ctx.db.query(SchoolClass)
            .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
            .first()
        )
    if school_class is None:
        name_value = (
            params.get("class_name") or params.get("class") or params.get("grade") or ""
        )
        school_class = access.find_class_by_name(ctx.db, ctx.org_id, name_value)
    if school_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find class '{params.get('class_name') or params.get('class')}' in your school. Ask the teacher to check the class name.",
        )
    return school_class


def _resolve_subject(ctx: OrgContext, params: dict):
    from ..models import Subject

    subject_id = params.get("subject_id")
    subject = None
    if subject_id:
        subject = (
            ctx.db.query(Subject)
            .filter(Subject.id == int(subject_id), Subject.organization_id == ctx.org_id)
            .first()
        )
    if subject is None:
        name_value = params.get("subject") or params.get("subject_name")
        subject = access.find_subject_by_name(ctx.db, ctx.org_id, name_value)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find subject '{params.get('subject')}' in your school.",
        )
    return subject


def _require_roles_or_individual(ctx: OrgContext, allowed: tuple) -> None:
    if ctx.is_individual:
        return
    if ctx.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not allow this action. Ask your school owner, principal or coordinator.",
        )


# ------------------------------------------------------------------
# Actions
# ------------------------------------------------------------------


@action(
    "view_marksheet",
    "Show the latest marksheet of a class for a subject (optionally filtered by test type).",
    "class_name (e.g. 'Class 8'), subject (e.g. 'Maths'), test_type (optional: weekly|monthly|mid_term|final_term)",
)
def view_marksheet(ctx: OrgContext, params: dict) -> dict:
    school_class = _resolve_class(ctx, params)
    subject = _resolve_subject(ctx, params)
    access.ensure_teacher_can_access(ctx.db, ctx, school_class.id, subject.id)

    query = (
        ctx.db.query(Marksheet)
        .filter(
            Marksheet.organization_id == ctx.org_id,
            Marksheet.class_id == school_class.id,
            Marksheet.subject_id == subject.id,
        )
        .order_by(Marksheet.created_at.desc())
    )
    test_type = params.get("test_type")
    if test_type:
        query = query.filter(Marksheet.exam_type == test_type)
    marksheet = query.first()
    if marksheet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No marksheet found for {school_class.name} {subject.name}."
            + (f" ({test_type})" if test_type else "")
            + " Upload a marksheet first from the Marksheets page.",
        )

    entries = (
        ctx.db.query(MarksheetEntry)
        .filter(MarksheetEntry.marksheet_id == marksheet.id)
        .order_by(MarksheetEntry.obtained_marks.desc())
        .all()
    )
    stats = analytics._stats_from_entries(entries)
    rows = [
        {
            "Roll No": e.student.roll_no if e.student else "",
            "Student": e.student.name if e.student else "",
            "Obtained": e.obtained_marks,
            "Total": e.total_marks,
            "%": analytics._entry_percent(e),
        }
        for e in entries
    ]
    return {
        "marksheet_id": marksheet.id,
        "title": marksheet.title,
        "class": school_class.name,
        "subject": subject.name,
        "exam_type": marksheet.exam_type,
        "total_marks": marksheet.total_marks,
        "stats": stats,
        "entries": rows,
        "display": {
            "type": "table",
            "title": marksheet.title,
            "columns": ["Roll No", "Student", "Obtained", "Total", "%"],
            "rows": rows[:15],
            "stats": [
                {"label": "Students", "value": stats["count"]},
                {"label": "Average", "value": stats["average"]},
                {"label": "Highest", "value": stats["highest"]},
                {"label": "Pass rate", "value": f"{stats['pass_rate']}%"},
            ],
            "route": f"/marksheets?open={marksheet.id}",
        },
    }


@action(
    "open_student_report",
    "Open the subject-wise performance report of one student.",
    "student_name (e.g. 'Ali Raza') or student_id",
)
def open_student_report(ctx: OrgContext, params: dict) -> dict:
    student = None
    student_id = params.get("student_id")
    if student_id:
        student = (
            ctx.db.query(Student)
            .filter(Student.id == int(student_id), Student.organization_id == ctx.org_id)
            .first()
        )
    if student is None:
        student = access.find_student_by_name(
            ctx.db, ctx.org_id, params.get("student_name") or params.get("name")
        )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find a student named '{params.get('student_name')}'.",
        )

    if ctx.member.role == ROLE_TEACHER and ctx.is_school:
        allowed_classes = access.visible_class_ids_for_teacher(ctx.db, ctx) or []
        if student.class_id not in allowed_classes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this student's class.",
            )

    performance = analytics.student_performance(ctx.db, ctx.org_id, student.id)
    rows = [
        {
            "Subject": s["subject_name"],
            "Assessments": s["assessments"],
            "Average %": s["average_percent"],
            "Grade": s["grade"],
        }
        for s in performance.get("subjects", [])
    ]
    return {
        "student": performance.get("student"),
        "subjects": performance.get("subjects"),
        "overall_percent": performance.get("overall_percent"),
        "overall_grade": performance.get("overall_grade"),
        "display": {
            "type": "table",
            "title": f"Report - {student.name} ({student.roll_no})",
            "columns": ["Subject", "Assessments", "Average %", "Grade"],
            "rows": rows,
            "stats": [
                {"label": "Overall", "value": f"{performance.get('overall_percent', 0)}%"},
                {"label": "Grade", "value": performance.get("overall_grade", "-")},
            ],
            "route": f"/reports?student_id={student.id}",
        },
    }


@action(
    "generate_worksheet",
    "Generate a new worksheet (practice sheet / homework) with AI for a class and subject.",
    "class_name, subject, topic (e.g. 'digestion'), difficulty (optional), language (optional)",
)
def generate_worksheet(ctx: OrgContext, params: dict) -> dict:
    school_class = _resolve_class(ctx, params)
    subject = _resolve_subject(ctx, params)
    topic = params.get("topic") or params.get("topics") or "general revision"
    language = params.get("language") or "en"

    request = WorksheetGenerateRequest(
        class_id=school_class.id,
        subject_id=subject.id,
        topic=topic,
        difficulty=params.get("difficulty") or "medium",
        language=language,
    )
    worksheet = create_worksheet(ctx.db, ctx, request)
    return {
        "worksheet_id": worksheet.id,
        "title": worksheet.title,
        "class": school_class.name,
        "subject": subject.name,
        "topic": topic,
        "has_answer_key": bool(worksheet.answer_key),
        "has_marking_scheme": bool(worksheet.marking_scheme),
        "display": {
            "type": "generated",
            "title": worksheet.title,
            "kind": "worksheet",
            "stats": [
                {"label": "Class", "value": school_class.name},
                {"label": "Subject", "value": subject.name},
                {"label": "Topic", "value": topic},
                {"label": "Answer key", "value": "Included" if worksheet.answer_key else "Not included"},
            ],
            "route": f"/worksheets?open={worksheet.id}",
        },
    }


def _generate_test_action(test_type: str, description: str):
    @action(
        f"generate_{test_type}_test",
        description,
        "class_name, subject, topic (optional), total_marks (optional number), language (optional)",
    )
    def handler(ctx: OrgContext, params: dict) -> dict:
        school_class = _resolve_class(ctx, params)
        subject = _resolve_subject(ctx, params)
        topic = params.get("topic") or params.get("topics")
        try:
            total_marks = int(params.get("total_marks") or 50)
        except (TypeError, ValueError):
            total_marks = 50

        request = TestGenerateRequest(
            class_id=school_class.id,
            subject_id=subject.id,
            test_type=test_type,
            topic=topic,
            total_marks=total_marks,
            difficulty=params.get("difficulty") or "medium",
            language=params.get("language") or "en",
        )
        test = create_test(ctx.db, ctx, request)
        label = {"weekly": "Weekly Test", "monthly": "Monthly Test"}.get(
            test_type, test_type.replace("_", " ").title()
        )
        return {
            "test_id": test.id,
            "title": test.title,
            "class": school_class.name,
            "subject": subject.name,
            "test_type": test_type,
            "total_marks": test.total_marks,
            "display": {
                "type": "generated",
                "title": test.title,
                "kind": label,
                "stats": [
                    {"label": "Class", "value": school_class.name},
                    {"label": "Subject", "value": subject.name},
                    {"label": "Total marks", "value": test.total_marks},
                    {"label": "Answer key", "value": "Included" if test.answer_key else "Not included"},
                ],
                "route": f"/tests?open={test.id}",
            },
        }

    return handler


_generate_test_action(
    "weekly", "Generate a weekly test paper (with answer key and marking scheme) for a class and subject."
)
_generate_test_action(
    "monthly", "Generate a monthly test paper (with answer key and marking scheme) for a class and subject."
)


@action(
    "show_class_performance",
    "Show class performance statistics. With a subject: subject-wise report. Without: all subjects of the class.",
    "class_name, subject (optional)",
)
def show_class_performance(ctx: OrgContext, params: dict) -> dict:
    school_class = _resolve_class(ctx, params)

    subject = None
    if params.get("subject") or params.get("subject_name"):
        subject = _resolve_subject(ctx, params)

    if subject is not None:
        access.ensure_teacher_can_access(ctx.db, ctx, school_class.id, subject.id)
        result = analytics.subject_performance(ctx.db, ctx.org_id, school_class.id, subject.id)
        marksheets = result.get("marksheets", [])
        rows = [
            {
                "Assessment": m["title"],
                "Type": (m.get("exam_type") or "-").replace("_", " ").title(),
                "Students": m["stats"]["count"],
                "Average %": m["stats"]["average_percent"],
                "Pass rate": f"{m['stats']['pass_rate']}%",
            }
            for m in marksheets[:10]
        ]
        stats = {
            "subject": subject.name,
            "marksheets": len(marksheets),
            "average_percent": round(
                sum(m["stats"]["average_percent"] for m in marksheets) / len(marksheets), 1
            )
            if marksheets
            else 0,
        }
    else:
        if ctx.member.role == ROLE_TEACHER and ctx.is_school:
            allowed = access.visible_class_ids_for_teacher(ctx.db, ctx) or []
            if school_class.id not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this class.",
                )
        result = analytics.class_report(ctx.db, ctx.org_id, school_class.id)
        rows = [
            {
                "Subject": s["subject_name"],
                "Assessments": s["marksheets"],
                "Students": s["stats"]["count"],
                "Average %": s["stats"]["average_percent"],
                "Pass rate": f"{s['stats']['pass_rate']}%",
            }
            for s in result.get("subjects", [])
        ]
        stats = {"subjects": len(rows)}

    return {
        "class": school_class.name,
        "subject": subject.name if subject else None,
        "stats": stats,
        "display": {
            "type": "table",
            "title": f"Performance - {school_class.name}" + (f" {subject.name}" if subject else ""),
            "columns": (
                ["Assessment", "Type", "Students", "Average %", "Pass rate"]
                if subject
                else ["Subject", "Assessments", "Students", "Average %", "Pass rate"]
            ),
            "rows": rows,
            "route": f"/reports?class_id={school_class.id}",
        },
    }


@action(
    "show_weak_students",
    "List students performing below the pass threshold (default 40%) in a class, optionally for one subject.",
    "class_name, subject (optional), threshold (optional number in percent)",
)
def show_weak_students(ctx: OrgContext, params: dict) -> dict:
    school_class = _resolve_class(ctx, params)
    subject = None
    if params.get("subject") or params.get("subject_name"):
        subject = _resolve_subject(ctx, params)
        access.ensure_teacher_can_access(ctx.db, ctx, school_class.id, subject.id)

    try:
        threshold = float(params.get("threshold") or 40)
    except (TypeError, ValueError):
        threshold = 40.0

    result = analytics.weak_students(
        ctx.db,
        ctx.org_id,
        school_class.id,
        subject_id=subject.id if subject else None,
        threshold_percent=threshold,
    )
    rows = [
        {
            "Roll No": s["roll_no"],
            "Student": s["student_name"],
            "Average %": s["average_percent"],
            "Grade": s["grade"],
        }
        for s in result.get("students", [])
    ]
    return {
        "class": school_class.name,
        "subject": subject.name if subject else "All subjects",
        "threshold": threshold,
        "students": result.get("students", []),
        "display": {
            "type": "table",
            "title": f"Weak students - {school_class.name} "
            + (subject.name if subject else "(all subjects)")
            + f" (below {threshold}%)",
            "columns": ["Roll No", "Student", "Average %", "Grade"],
            "rows": rows[:20],
            "route": f"/reports?class_id={school_class.id}&tab=weak",
        },
    }


@action(
    "create_final_report",
    "Create the final term consolidated report for a class (coordinator/principal action).",
    "class_name, section_name (optional), academic_year (optional)",
    allowed_roles=(ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_COORDINATOR),
)
def create_final_report(ctx: OrgContext, params: dict) -> dict:
    _require_roles_or_individual(
        ctx, (ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_COORDINATOR)
    )
    school_class = _resolve_class(ctx, params)

    section_id = None
    section_name = params.get("section_name") or params.get("section")
    if section_name:
        from ..models import Section

        section = (
            ctx.db.query(Section)
            .filter(
                Section.organization_id == ctx.org_id,
                Section.class_id == school_class.id,
                Section.name.ilike(f"%{str(section_name).strip()}%"),
            )
            .first()
        )
        if section is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not find section '{section_name}' in {school_class.name}.",
            )
        section_id = section.id

    report = analytics.build_final_term_report(
        ctx.db,
        ctx.org_id,
        school_class.id,
        section_id=section_id,
        generated_by_id=ctx.user.id,
        academic_year=params.get("academic_year"),
    )
    content = report.content or {}
    return {
        "report_id": report.id,
        "title": report.title,
        "class": school_class.name,
        "students": len(content.get("students", [])),
        "class_average": content.get("class_average"),
        "display": {
            "type": "generated",
            "title": report.title,
            "kind": "Final Term Report",
            "stats": [
                {"label": "Class", "value": school_class.name},
                {"label": "Students", "value": len(content.get("students", []))},
                {"label": "Class average", "value": f"{content.get('class_average', 0)}%"},
                {"label": "Marksheets included", "value": content.get("marksheets_included", 0)},
            ],
            "route": f"/reports?report_id={report.id}",
        },
    }


@action(
    "invite_teacher",
    "Invite a teacher to join the school (school owner action). Respects teacher seat limits.",
    "email, full_name (optional), role (optional: teacher|subject_coordinator|principal)",
    allowed_roles=(ROLE_ORG_ADMIN,),
)
def invite_teacher(ctx: OrgContext, params: dict) -> dict:
    if ctx.is_individual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Individual teacher accounts do not need invitations. "
            "Create a school account to invite teachers.",
        )
    _require_roles_or_individual(ctx, (ROLE_ORG_ADMIN,))

    email = (params.get("email") or "").strip().lower()
    full_name = (params.get("full_name") or params.get("name") or "").strip()
    role = params.get("role") or ROLE_TEACHER
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid teacher email address.",
        )
    access.ensure_valid_role(role)
    access.ensure_seat_available(ctx.db, ctx.organization)

    invite_code = secrets.token_hex(6).upper()
    invite = TeacherInvite(
        organization_id=ctx.org_id,
        email=email,
        full_name=full_name or None,
        role=role,
        invite_code=invite_code,
        created_by_id=ctx.user.id,
    )
    ctx.db.add(invite)
    ctx.db.commit()
    ctx.db.refresh(invite)

    usage = access.seat_usage(ctx.db, ctx.organization)
    return {
        "invite_id": invite.id,
        "email": email,
        "role": role,
        "invite_code": invite_code,
        "invite_link": f"/invite?code={invite_code}",
        "seats_remaining": usage["seats_remaining"],
        "display": {
            "type": "message",
            "title": "Invitation created",
            "text": (
                f"Invite code {invite_code} created for {email}. Share this link: "
                f"/invite?code={invite_code} - the teacher signs up with the code. "
                f"Seats remaining: {usage['seats_remaining']}."
            ),
            "route": "/admin",
        },
    }


@action(
    "check_teacher_seat_limit",
    "Check how many teacher seats the school has used and how many are free.",
    "",
)
def check_teacher_seat_limit(ctx: OrgContext, params: dict) -> dict:
    usage = access.seat_usage(ctx.db, ctx.organization)
    if not usage["applies"]:
        return {
            "applies": False,
            "display": {
                "type": "message",
                "title": "Teacher seats",
                "text": "You are using a free individual teacher account. "
                "Teacher seat limits apply to school accounts only.",
            },
        }
    return {
        "applies": True,
        "seats_total": usage["seats_total"],
        "seats_used": usage["seats_used"],
        "seats_remaining": usage["seats_remaining"],
        "plan": usage["plan_name"],
        "display": {
            "type": "stats",
            "title": "Teacher seats",
            "stats": [
                {"label": "Plan", "value": usage["plan_name"] or "-"},
                {"label": "Seats used", "value": f"{usage['seats_used']} / {usage['seats_total']}"},
                {"label": "Seats free", "value": usage["seats_remaining"]},
            ],
            "route": "/admin",
        },
    }


PAGE_ROUTES = {
    "dashboard": ("/dashboard", "Teacher Dashboard"),
    "teacher": ("/dashboard", "Teacher Dashboard"),
    "admin": ("/admin", "School Admin"),
    "owner": ("/admin", "School Admin"),
    "coordinator": ("/coordinator", "Coordinator Dashboard"),
    "principal": ("/coordinator", "Coordinator Dashboard"),
    "setup": ("/setup", "Class & Student Setup"),
    "worksheets": ("/worksheets", "Worksheet Generator"),
    "tests": ("/tests", "Test Generator"),
    "marksheets": ("/marksheets", "Marksheets"),
    "reports": ("/reports", "Reports"),
}


@action(
    "open_dashboard_page",
    "Open a page of the SchoolAssist dashboard for the user.",
    "page (one of: dashboard, admin, coordinator, setup, worksheets, tests, marksheets, reports)",
)
def open_dashboard_page(ctx: OrgContext, params: dict) -> dict:
    page = (params.get("page") or "").strip().lower()
    route, label = PAGE_ROUTES.get(page, ("/dashboard", "Teacher Dashboard"))
    if route == "/admin" and not (ctx.is_owner or ctx.is_individual):
        route, label = ("/dashboard", "Teacher Dashboard")
    if route == "/coordinator" and not (ctx.is_academic_lead or ctx.is_individual):
        route, label = ("/dashboard", "Teacher Dashboard")
    return {
        "page": page,
        "route": route,
        "display": {
            "type": "route",
            "title": label,
            "text": f"Opening {label}...",
            "route": route,
        },
    }


def get_action_catalog() -> str:
    """Human-readable action list for the chatbot system prompt."""
    lines = []
    for spec in ACTION_REGISTRY.values():
        lines.append(f"- {spec.name}: {spec.description} | params: {spec.params or 'none'}")
    return "\n".join(lines)
