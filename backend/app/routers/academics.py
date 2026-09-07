"""Academic setup: classes, sections, subjects, students and teacher assignments."""

import re
import secrets
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import OrgContext, get_org_context, require_roles
from ..models import (
    ROLE_COORDINATOR,
    ROLE_ORG_ADMIN,
    ROLE_PRINCIPAL,
    ROLE_TEACHER,
    ROLE_VICE_PRINCIPAL,
    Announcement,
    ClassSubject,
    ExamSchedule,
    Guardian,
    Marksheet,
    MarksheetEntry,
    OrganizationMember,
    Report,
    SchoolClass,
    Section,
    SeatingPlan,
    Student,
    StudentAttendance,
    StudentGuardian,
    Subject,
    Teacher,
    TeacherSubject,
    TeacherSubjectAssignment,
    TimetableEntry,
    User,
    Worksheet,
    Test,
)
from ..schemas import (
    ClassCreate,
    ClassSubjectsUpdate,
    ClassUpdate,
    GuardianCreate,
    GuardianUpdate,
    SectionCreate,
    SectionUpdate,
    StudentCreate,
    StudentGuardianLink,
    StudentImportRow,
    StudentUpdate,
    SubjectCreate,
    SubjectUpdate,
    TeacherAssignmentCreate,
    TeacherCreateRequest,
    TeacherSubjectsUpdate,
    TeacherUpdateRequest,
)
from ..services import mailer
from ..services.access import ensure_seat_available, ensure_valid_role
from ..services.seed import assign_default_subjects
from ..services.tabular import read_table

router = APIRouter(prefix="/academics", tags=["academics"])

MANAGER_ROLES = (ROLE_ORG_ADMIN, ROLE_PRINCIPAL, ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR)


def _can_manage(ctx: OrgContext) -> bool:
    """Class/section/subject/student management is for academic leads.
    Individual teacher accounts manage their own personal workspace."""
    return ctx.is_individual or ctx.role in MANAGER_ROLES


def _require_manager(ctx: OrgContext) -> None:
    if not _can_manage(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ask your school owner, principal or coordinator to change the academic setup.",
        )


# Deleting a class, section or subject that other rows still point at would break
# the foreign keys, so each delete first reports what is in the way.
_CLASS_DEPENDENCIES = (
    ("sections", Section),
    ("students", Student),
    ("timetable periods", TimetableEntry),
    ("exam papers", ExamSchedule),
    ("teacher assignments", TeacherSubjectAssignment),
    ("worksheets", Worksheet),
    ("tests", Test),
    ("marksheets", Marksheet),
    ("seating plans", SeatingPlan),
)

_SUBJECT_DEPENDENCIES = (
    ("timetable periods", TimetableEntry),
    ("exam papers", ExamSchedule),
    ("teacher assignments", TeacherSubjectAssignment),
    ("worksheets", Worksheet),
    ("tests", Test),
    ("marksheets", Marksheet),
    ("reports", Report),
)

# Rows that keep an optional section link; the history stays but the link is cleared.
_SECTION_REFERENCES = (
    Announcement,
    StudentAttendance,
    TimetableEntry,
    TeacherSubjectAssignment,
    Worksheet,
    Test,
    Marksheet,
    Report,
)


def _usage_labels(ctx: OrgContext, column: str, record_id: int, dependencies) -> list[str]:
    """Human-readable names of the records that still reference ``record_id``."""
    labels = []
    for label, model in dependencies:
        used = (
            ctx.db.query(model)
            .filter(
                model.organization_id == ctx.org_id,
                getattr(model, column) == record_id,
            )
            .count()
        )
        if used:
            labels.append(label)
    return labels


# ------------------------------------------------------------------
# Classes
# ------------------------------------------------------------------


def _grade_from_name(name: str) -> Optional[int]:
    match = re.search(r"\d+", name or "")
    return int(match.group()) if match else None


def _class_level(grade_level: Optional[int], name: str) -> Optional[str]:
    """Primary covers grades 1-5, secondary covers 6-10."""
    grade = grade_level if grade_level is not None else _grade_from_name(name)
    if grade is None:
        return None
    if 1 <= grade <= 5:
        return "primary"
    if 6 <= grade <= 10:
        return "secondary"
    return None


@router.get("/classes")
def list_classes(ctx: OrgContext = Depends(get_org_context)):
    classes = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.organization_id == ctx.org_id)
        .order_by(SchoolClass.id.asc())
        .all()
    )
    # Class teachers are shown by name on the Classes & Sections cards.
    teacher_ids = {
        row[0]
        for row in ctx.db.query(Section.class_teacher_id)
        .filter(
            Section.organization_id == ctx.org_id,
            Section.class_teacher_id.isnot(None),
        )
        .all()
    }
    teacher_names = {
        user.id: user.full_name
        for user in ctx.db.query(User).filter(User.id.in_(teacher_ids or {0})).all()
    }
    result = []
    for school_class in classes:
        sections = (
            ctx.db.query(Section)
            .filter(Section.class_id == school_class.id)
            .order_by(Section.name.asc())
            .all()
        )
        students = (
            ctx.db.query(Student)
            .filter(
                Student.class_id == school_class.id, Student.is_active.is_(True)
            )
            .count()
        )
        # Each section is shown as its own card, so it needs its own headcount.
        section_students = dict(
            ctx.db.query(Student.section_id, func.count(Student.id))
            .filter(
                Student.class_id == school_class.id,
                Student.is_active.is_(True),
                Student.section_id.isnot(None),
            )
            .group_by(Student.section_id)
            .all()
        )
        result.append(
            {
                "id": school_class.id,
                "name": school_class.name,
                "grade_level": school_class.grade_level,
                "level": _class_level(school_class.grade_level, school_class.name),
                "capacity": school_class.capacity,
                "students": students,
                "sections": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "class_id": s.class_id,
                        "class_teacher_id": s.class_teacher_id,
                        "students": section_students.get(s.id, 0),
                        "class_teacher": (
                            teacher_names.get(s.class_teacher_id) if s.class_teacher_id else None
                        ),
                    }
                    for s in sections
                ],
            }
        )
    return result


@router.post("/classes")
def create_class(payload: ClassCreate, ctx: OrgContext = Depends(get_org_context)):
    _require_manager(ctx)
    school_class = SchoolClass(
        organization_id=ctx.org_id,
        name=payload.name.strip(),
        grade_level=(
            payload.grade_level
            if payload.grade_level is not None
            else _grade_from_name(payload.name.strip())
        ),
        capacity=payload.capacity,
    )
    ctx.db.add(school_class)
    ctx.db.commit()
    ctx.db.refresh(school_class)
    assign_default_subjects(ctx.db, ctx.org_id, school_class)
    return {
        "id": school_class.id,
        "name": school_class.name,
        "grade_level": school_class.grade_level,
        "level": _class_level(school_class.grade_level, school_class.name),
        "capacity": school_class.capacity,
    }


@router.patch("/classes/{class_id}")
def update_class(
    class_id: int, payload: ClassUpdate, ctx: OrgContext = Depends(get_org_context)
):
    """Rename a class, move its grade level or set the strength cap.
    Sending ``capacity: null`` removes the cap."""
    _require_manager(ctx)
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if payload.name is not None:
        school_class.name = payload.name.strip()
    provided = payload.model_fields_set
    for field in ("grade_level", "capacity"):
        if field in provided:
            setattr(school_class, field, getattr(payload, field))
    if payload.name is not None and "grade_level" not in provided:
        # Renaming "Class 5" to "Class 8" must also move it from primary to
        # secondary, so re-read the grade from the new name.
        derived = _grade_from_name(school_class.name)
        if derived is not None:
            school_class.grade_level = derived
    ctx.db.commit()
    return {
        "id": school_class.id,
        "name": school_class.name,
        "grade_level": school_class.grade_level,
        "level": _class_level(school_class.grade_level, school_class.name),
        "capacity": school_class.capacity,
    }


@router.delete("/classes/{class_id}")
def delete_class(class_id: int, ctx: OrgContext = Depends(get_org_context)):
    """Remove an empty class. Anything still attached to it is reported back
    so the admin knows what to move first instead of hitting a database error."""
    _require_manager(ctx)
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    blocking = _usage_labels(ctx, "class_id", class_id, _CLASS_DEPENDENCIES)
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This class still has {', '.join(blocking)}. "
                "Move or remove them before deleting the class."
            ),
        )
    ctx.db.query(ClassSubject).filter(
        ClassSubject.organization_id == ctx.org_id, ClassSubject.class_id == class_id
    ).delete()
    # Class-scoped announcements keep their text but become school-wide.
    ctx.db.query(Announcement).filter(
        Announcement.organization_id == ctx.org_id, Announcement.class_id == class_id
    ).update({"class_id": None, "audience": "school"}, synchronize_session=False)
    ctx.db.delete(school_class)
    ctx.db.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Sections
# ------------------------------------------------------------------


@router.post("/sections")
def create_section(payload: SectionCreate, ctx: OrgContext = Depends(get_org_context)):
    _require_manager(ctx)
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == payload.class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    section = Section(
        organization_id=ctx.org_id,
        class_id=payload.class_id,
        name=payload.name.strip(),
        class_teacher_id=payload.class_teacher_id,
    )
    ctx.db.add(section)
    ctx.db.commit()
    ctx.db.refresh(section)
    return {
        "id": section.id,
        "name": section.name,
        "class_id": section.class_id,
        "class_teacher_id": section.class_teacher_id,
    }


@router.patch("/sections/{section_id}")
def update_section(
    section_id: int, payload: SectionUpdate, ctx: OrgContext = Depends(get_org_context)
):
    """Rename a section or change its class teacher (null clears the teacher)."""
    _require_manager(ctx)
    section = (
        ctx.db.query(Section)
        .filter(Section.id == section_id, Section.organization_id == ctx.org_id)
        .first()
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    if payload.name is not None:
        section.name = payload.name.strip()
    if "class_teacher_id" in payload.model_fields_set:
        teacher_id = payload.class_teacher_id
        if teacher_id is not None:
            member = (
                ctx.db.query(OrganizationMember)
                .filter(
                    OrganizationMember.organization_id == ctx.org_id,
                    OrganizationMember.user_id == teacher_id,
                    OrganizationMember.is_active.is_(True),
                )
                .first()
            )
            if member is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="That teacher is not an active member of this school.",
                )
        section.class_teacher_id = teacher_id
    ctx.db.commit()
    return {
        "id": section.id,
        "name": section.name,
        "class_id": section.class_id,
        "class_teacher_id": section.class_teacher_id,
    }


@router.delete("/sections/{section_id}")
def delete_section(section_id: int, ctx: OrgContext = Depends(get_org_context)):
    """Remove a section. Its students must be moved to another section (or to the
    whole class) first; older records keep their history with the link cleared."""
    _require_manager(ctx)
    section = (
        ctx.db.query(Section)
        .filter(Section.id == section_id, Section.organization_id == ctx.org_id)
        .first()
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    enrolled = (
        ctx.db.query(Student)
        .filter(
            Student.organization_id == ctx.org_id,
            Student.section_id == section_id,
            Student.is_active.is_(True),
        )
        .count()
    )
    if enrolled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{enrolled} active student{'s' if enrolled != 1 else ''} "
                "are still in this section. Move them to another section first."
            ),
        )
    ctx.db.query(Student).filter(
        Student.organization_id == ctx.org_id, Student.section_id == section_id
    ).update({"section_id": None}, synchronize_session=False)
    for model in _SECTION_REFERENCES:
        ctx.db.query(model).filter(
            model.organization_id == ctx.org_id, model.section_id == section_id
        ).update({"section_id": None}, synchronize_session=False)
    ctx.db.delete(section)
    ctx.db.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Subjects
# ------------------------------------------------------------------


@router.get("/subjects")
def list_subjects(
    class_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    if class_id:
        school_class = (
            ctx.db.query(SchoolClass)
            .filter(
                SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id
            )
            .first()
        )
        if school_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
        # Legacy classes get their default subject list on first use
        assign_default_subjects(ctx.db, ctx.org_id, school_class)
        subjects = (
            ctx.db.query(Subject)
            .join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .filter(
                ClassSubject.organization_id == ctx.org_id,
                ClassSubject.class_id == class_id,
            )
            .order_by(Subject.name.asc())
            .all()
        )
    else:
        subjects = (
            ctx.db.query(Subject)
            .filter(Subject.organization_id == ctx.org_id)
            .order_by(Subject.name.asc())
            .all()
        )
    return [{"id": s.id, "name": s.name, "code": s.code} for s in subjects]


@router.post("/subjects")
def create_subject(payload: SubjectCreate, ctx: OrgContext = Depends(get_org_context)):
    _require_manager(ctx)
    existing = (
        ctx.db.query(Subject)
        .filter(
            Subject.organization_id == ctx.org_id,
            Subject.name.ilike(payload.name.strip()),
        )
        .first()
    )
    if existing is not None:
        return {"id": existing.id, "name": existing.name, "code": existing.code}
    subject = Subject(
        organization_id=ctx.org_id,
        name=payload.name.strip(),
        code=payload.code,
    )
    ctx.db.add(subject)
    ctx.db.commit()
    ctx.db.refresh(subject)
    return {"id": subject.id, "name": subject.name, "code": subject.code}


@router.patch("/subjects/{subject_id}")
def update_subject(
    subject_id: int, payload: SubjectUpdate, ctx: OrgContext = Depends(get_org_context)
):
    """Rename a subject or change its short code (``code: null`` clears it)."""
    _require_manager(ctx)
    subject = (
        ctx.db.query(Subject)
        .filter(Subject.id == subject_id, Subject.organization_id == ctx.org_id)
        .first()
    )
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")
    if payload.name is not None:
        name = payload.name.strip()
        clash = (
            ctx.db.query(Subject)
            .filter(
                Subject.organization_id == ctx.org_id,
                Subject.name.ilike(name),
                Subject.id != subject_id,
            )
            .first()
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A subject called {name} already exists.",
            )
        subject.name = name
    if "code" in payload.model_fields_set:
        subject.code = payload.code.strip() if payload.code else None
    ctx.db.commit()
    return {"id": subject.id, "name": subject.name, "code": subject.code}


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, ctx: OrgContext = Depends(get_org_context)):
    """Remove a subject that is not part of any result, test or timetable yet.
    Class subject lists and "can teach" links are dropped automatically."""
    _require_manager(ctx)
    subject = (
        ctx.db.query(Subject)
        .filter(Subject.id == subject_id, Subject.organization_id == ctx.org_id)
        .first()
    )
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")
    blocking = _usage_labels(ctx, "subject_id", subject_id, _SUBJECT_DEPENDENCIES)
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{subject.name} is already used in {', '.join(blocking)}. "
                "Remove those records before deleting the subject."
            ),
        )
    ctx.db.query(ClassSubject).filter(
        ClassSubject.organization_id == ctx.org_id, ClassSubject.subject_id == subject_id
    ).delete()
    ctx.db.query(TeacherSubject).filter(
        TeacherSubject.organization_id == ctx.org_id, TeacherSubject.subject_id == subject_id
    ).delete()
    ctx.db.delete(subject)
    ctx.db.commit()
    return {"status": "deleted"}


@router.get("/classes/{class_id}/subjects")
def list_class_subjects(class_id: int, ctx: OrgContext = Depends(get_org_context)):
    """Subject ids taught in a class (used by the Setup editor)."""
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    assign_default_subjects(ctx.db, ctx.org_id, school_class)
    rows = (
        ctx.db.query(ClassSubject.subject_id)
        .filter(
            ClassSubject.organization_id == ctx.org_id, ClassSubject.class_id == class_id
        )
        .all()
    )
    return {"class_id": class_id, "subject_ids": [row[0] for row in rows]}


@router.put("/classes/{class_id}/subjects")
def set_class_subjects(
    class_id: int, payload: ClassSubjectsUpdate, ctx: OrgContext = Depends(get_org_context)
):
    """Replace the subject list of a class (Setup > Subjects per class)."""
    _require_manager(ctx)
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    valid_ids = [
        row[0]
        for row in ctx.db.query(Subject.id)
        .filter(
            Subject.organization_id == ctx.org_id, Subject.id.in_(payload.subject_ids or [])
        )
        .all()
    ]
    ctx.db.query(ClassSubject).filter(
        ClassSubject.organization_id == ctx.org_id, ClassSubject.class_id == class_id
    ).delete()
    for subject_id in sorted(valid_ids):
        ctx.db.add(
            ClassSubject(
                organization_id=ctx.org_id, class_id=class_id, subject_id=subject_id
            )
        )
    ctx.db.commit()
    return {"class_id": class_id, "subject_ids": sorted(valid_ids)}


# ------------------------------------------------------------------
# Students
# ------------------------------------------------------------------


@router.get("/students")
def list_students(
    class_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    ctx: OrgContext = Depends(get_org_context),
):
    """Active students by default; the admin Students page passes
    ``include_inactive`` so it can show and re-activate archived records.
    ``search`` matches the name or the roll number."""
    query = ctx.db.query(Student).filter(Student.organization_id == ctx.org_id)
    if not include_inactive:
        query = query.filter(Student.is_active.is_(True))
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if section_id:
        query = query.filter(Student.section_id == section_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Student.name.ilike(term), Student.roll_no.ilike(term)))
    students = (
        query.order_by(Student.is_active.desc(), Student.roll_no.asc()).limit(500).all()
    )

    class_names = {
        c.id: c.name
        for c in ctx.db.query(SchoolClass)
        .filter(SchoolClass.organization_id == ctx.org_id)
        .all()
    }
    section_names = {
        s.id: s.name
        for s in ctx.db.query(Section).filter(Section.organization_id == ctx.org_id).all()
    }
    return [
        {
            "id": s.id,
            "name": s.name,
            "roll_no": s.roll_no,
            "class_id": s.class_id,
            "class": class_names.get(s.class_id, ""),
            "section_id": s.section_id,
            "section": section_names.get(s.section_id) if s.section_id else None,
            "guardian_name": s.guardian_name,
            "guardian_phone": s.guardian_phone,
            "is_active": bool(s.is_active),
        }
        for s in students
    ]


@router.post("/students")
def create_student(payload: StudentCreate, ctx: OrgContext = Depends(get_org_context)):
    _require_manager(ctx)
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == payload.class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")

    duplicate = (
        ctx.db.query(Student)
        .filter(
            Student.organization_id == ctx.org_id,
            Student.class_id == payload.class_id,
            Student.roll_no == payload.roll_no.strip(),
        )
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roll no {payload.roll_no} already exists in this class.",
        )

    student = Student(
        organization_id=ctx.org_id,
        class_id=payload.class_id,
        section_id=payload.section_id,
        roll_no=payload.roll_no.strip(),
        name=payload.name.strip(),
        guardian_name=payload.guardian_name,
        guardian_phone=payload.guardian_phone,
    )
    ctx.db.add(student)
    ctx.db.commit()
    ctx.db.refresh(student)
    return {"id": student.id, "name": student.name, "roll_no": student.roll_no}


@router.patch("/students/{student_id}")
def update_student(
    student_id: int, payload: StudentUpdate, ctx: OrgContext = Depends(get_org_context)
):
    _require_manager(ctx)
    student = (
        ctx.db.query(Student)
        .filter(Student.id == student_id, Student.organization_id == ctx.org_id)
        .first()
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    provided = payload.model_fields_set
    class_changed = False
    if payload.class_id is not None and payload.class_id != student.class_id:
        new_class = (
            ctx.db.query(SchoolClass)
            .filter(SchoolClass.id == payload.class_id, SchoolClass.organization_id == ctx.org_id)
            .first()
        )
        if new_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
        student.class_id = payload.class_id
        class_changed = True
    for field in ("roll_no", "name"):
        value = getattr(payload, field)
        if value is not None:
            setattr(student, field, value)
    # Guardian details are optional text, so an explicit null clears them.
    for field in ("guardian_name", "guardian_phone"):
        if field in provided:
            setattr(student, field, getattr(payload, field))
    # "— whole class —" sends section_id: null, which must be honoured.
    if "section_id" in provided:
        if payload.section_id is None:
            student.section_id = None
        else:
            section = (
                ctx.db.query(Section)
                .filter(Section.id == payload.section_id, Section.organization_id == ctx.org_id)
                .first()
            )
            if section is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
            student.section_id = section.id
    elif class_changed:
        # The previous section belongs to the old class.
        student.section_id = None
    if payload.is_active is not None:
        student.is_active = payload.is_active
    ctx.db.commit()
    return {"id": student.id, "name": student.name, "roll_no": student.roll_no}


@router.delete("/students/{student_id}")
def deactivate_student(student_id: int, ctx: OrgContext = Depends(get_org_context)):
    _require_manager(ctx)
    student = (
        ctx.db.query(Student)
        .filter(Student.id == student_id, Student.organization_id == ctx.org_id)
        .first()
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    student.is_active = False
    ctx.db.commit()
    return {"status": "deactivated"}


@router.post("/students/import")
async def import_students(
    file: UploadFile = File(...),
    class_id: int = Form(...),
    ctx: OrgContext = Depends(get_org_context),
):
    """Bulk import students from an Excel/CSV file.
    Expected columns (any order): roll_no, name, section (optional), guardian (optional)."""
    _require_manager(ctx)
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")

    content = await file.read()
    try:
        columns, rows = read_table(content, file.filename)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the file. Upload .xlsx or .csv with columns: roll_no, name, section.",
        )

    roll_col = next((c for c in columns if "roll" in c), None)
    name_col = next((c for c in columns if c in ("name", "student", "student_name")), None)
    section_col = next((c for c in columns if "section" in c), None)
    if roll_col is None or name_col is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must include a roll number column and a name column.",
        )

    sections = (
        ctx.db.query(Section).filter(Section.class_id == class_id).all()
    )
    section_map = {s.name.strip().upper(): s.id for s in sections}

    created = 0
    skipped: list[str] = []
    for row in rows:
        roll_no = str(row[roll_col]).strip()
        name = str(row[name_col]).strip()
        if not roll_no or not name or roll_no.lower() == "nan":
            continue
        duplicate = (
            ctx.db.query(Student)
            .filter(
                Student.organization_id == ctx.org_id,
                Student.class_id == class_id,
                Student.roll_no == roll_no,
            )
            .first()
        )
        if duplicate is not None:
            skipped.append(f"{roll_no} - {name}")
            continue
        section_id = None
        if section_col and str(row.get(section_col, "")).strip().upper() in section_map:
            section_id = section_map[str(row[section_col]).strip().upper()]
        ctx.db.add(
            Student(
                organization_id=ctx.org_id,
                class_id=class_id,
                section_id=section_id,
                roll_no=roll_no,
                name=name,
            )
        )
        created += 1
    ctx.db.commit()
    return {"created": created, "skipped_duplicates": skipped[:20]}


# ------------------------------------------------------------------
# Teacher subject assignments
# ------------------------------------------------------------------


def _assignment_rows(db: Session, ctx: OrgContext, assignments):
    class_names = {
        c.id: c.name
        for c in db.query(SchoolClass).filter(SchoolClass.organization_id == ctx.org_id).all()
    }
    subject_names = {
        s.id: s.name
        for s in db.query(Subject).filter(Subject.organization_id == ctx.org_id).all()
    }
    # Load members of this org for teacher names
    from ..models import OrganizationMember

    members = (
        db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == ctx.org_id)
        .all()
    )
    teacher_names = {user.id: user.full_name for _, user in members}

    section_names = {
        s.id: s.name for s in db.query(Section).filter(Section.organization_id == ctx.org_id).all()
    }
    return [
        {
            "id": a.id,
            "teacher_id": a.teacher_id,
            "teacher_name": teacher_names.get(a.teacher_id, ""),
            "class_id": a.class_id,
            "class": class_names.get(a.class_id, ""),
            "section_id": a.section_id,
            "section": section_names.get(a.section_id) if a.section_id else None,
            "subject_id": a.subject_id,
            "subject": subject_names.get(a.subject_id, ""),
            "academic_year": a.academic_year,
        }
        for a in assignments
    ]


@router.get("/teacher-assignments")
def list_assignments(ctx: OrgContext = Depends(get_org_context)):
    query = ctx.db.query(TeacherSubjectAssignment).filter(
        TeacherSubjectAssignment.organization_id == ctx.org_id
    )
    if ctx.member.role == ROLE_TEACHER and ctx.is_school:
        query = query.filter(TeacherSubjectAssignment.teacher_id == ctx.user.id)
    assignments = query.order_by(TeacherSubjectAssignment.class_id.asc()).all()
    return _assignment_rows(ctx.db, ctx, assignments)


@router.post("/teacher-assignments")
def create_assignment(
    payload: TeacherAssignmentCreate, ctx: OrgContext = Depends(get_org_context)
):
    if ctx.role not in (ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher allocation is managed by a vice principal or coordinator.",
        )
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == payload.class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    subject = (
        ctx.db.query(Subject)
        .filter(Subject.id == payload.subject_id, Subject.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None or subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class or subject not found."
        )
    if payload.section_id is not None:
        section = ctx.db.query(Section).filter(Section.id == payload.section_id, Section.class_id == payload.class_id, Section.organization_id == ctx.org_id).first()
        if section is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section does not belong to the selected class.")
    allowed_subject = ctx.db.query(ClassSubject).filter(ClassSubject.organization_id == ctx.org_id, ClassSubject.class_id == payload.class_id, ClassSubject.subject_id == payload.subject_id).first()
    if allowed_subject is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This subject is not assigned to the selected class.")
    duplicate = (
        ctx.db.query(TeacherSubjectAssignment)
        .filter(
            TeacherSubjectAssignment.organization_id == ctx.org_id,
            TeacherSubjectAssignment.teacher_id == payload.teacher_id,
            TeacherSubjectAssignment.class_id == payload.class_id,
            TeacherSubjectAssignment.subject_id == payload.subject_id,
        )
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This teacher is already assigned to this class and subject.",
        )
    assignment = TeacherSubjectAssignment(
        organization_id=ctx.org_id,
        teacher_id=payload.teacher_id,
        class_id=payload.class_id,
        section_id=payload.section_id,
        subject_id=payload.subject_id,
        academic_year=payload.academic_year,
    )
    ctx.db.add(assignment)
    ctx.db.commit()
    ctx.db.refresh(assignment)
    return _assignment_rows(ctx.db, ctx, [assignment])[0]


@router.delete("/teacher-assignments/{assignment_id}")
def delete_assignment(assignment_id: int, ctx: OrgContext = Depends(get_org_context)):
    if ctx.role not in (ROLE_VICE_PRINCIPAL, ROLE_COORDINATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher allocation is managed by a vice principal or coordinator.",
        )
    assignment = (
        ctx.db.query(TeacherSubjectAssignment)
        .filter(
            TeacherSubjectAssignment.id == assignment_id,
            TeacherSubjectAssignment.organization_id == ctx.org_id,
        )
        .first()
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    ctx.db.delete(assignment)
    ctx.db.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Teacher directory (for assignment forms)
# ------------------------------------------------------------------


def _teacher_level(value: Optional[str]) -> Optional[str]:
    """Only primary (classes 1-5) and secondary (6-10) are stored; anything
    else — including a blank selection — means the teacher covers both."""
    cleaned = (value or "").strip().lower()
    return cleaned if cleaned in ("primary", "secondary") else None


@router.get("/teachers")
def list_teachers(ctx: OrgContext = Depends(get_org_context)):
    """Staff directory with profile data (used by assignment forms and the
    Teachers management page)."""
    members = (
        ctx.db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == ctx.org_id)
        .order_by(User.full_name.asc())
        .all()
    )
    profiles = {
        t.user_id: t
        for t in ctx.db.query(Teacher).filter(Teacher.organization_id == ctx.org_id).all()
    }
    # Accounts created outside the Teachers page (owner signup, invite joins)
    # deserve an employee id too: backfill a profile for any member missing one.
    default_designation = {
        ROLE_ORG_ADMIN: "School Owner",
        ROLE_PRINCIPAL: "Principal",
        ROLE_COORDINATOR: "Subject Coordinator",
    }
    added_profile = False
    for member, user in members:
        if user.id in profiles:
            continue
        profile = Teacher(
            organization_id=ctx.org_id,
            user_id=user.id,
            employee_id=_new_employee_id(ctx.db, ctx.org_id),
            designation=default_designation.get(member.role, "Teacher"),
        )
        ctx.db.add(profile)
        profiles[user.id] = profile
        added_profile = True
    if added_profile:
        ctx.db.commit()
    subject_rows = (
        ctx.db.query(TeacherSubject)
        .filter(TeacherSubject.organization_id == ctx.org_id)
        .all()
    )
    subjects_by_teacher: dict[int, list[int]] = {}
    for row in subject_rows:
        subjects_by_teacher.setdefault(row.teacher_id, []).append(row.subject_id)
    return [
        {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": member.role,
            "is_active": member.is_active,
            "member_id": member.id,
            "employee_id": profiles[user.id].employee_id if user.id in profiles else None,
            "designation": profiles[user.id].designation if user.id in profiles else None,
            "level": profiles[user.id].level if user.id in profiles else None,
            "department": profiles[user.id].department if user.id in profiles else None,
            "qualification": profiles[user.id].qualification if user.id in profiles else None,
            "gender": profiles[user.id].gender if user.id in profiles else None,
            "status": profiles[user.id].status if user.id in profiles else "active",
            "subject_ids": subjects_by_teacher.get(user.id, []),
        }
        for member, user in members
    ]


def _new_employee_id(db: Session, org_id: int) -> str:
    employee_id = f"T-{org_id}-{secrets.token_hex(3).upper()}"
    while db.query(Teacher).filter(Teacher.organization_id == org_id, Teacher.employee_id == employee_id).first():
        employee_id = f"T-{org_id}-{secrets.token_hex(3).upper()}"
    return employee_id


@router.post("/teachers")
def create_teacher(
    payload: TeacherCreateRequest, ctx: OrgContext = Depends(get_org_context)
):
    """Create a teacher/staff member together with their login account.
    Credentials are emailed when SMTP is configured, otherwise surfaced once."""
    if ctx.role != ROLE_ORG_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the admin can create staff accounts.",
        )
    ensure_valid_role(payload.role)
    ensure_seat_available(ctx.db, ctx.organization)

    email = payload.email.lower()
    existing_member = (
        ctx.db.query(OrganizationMember)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == ctx.org_id, User.email == email)
        .first()
    )
    if existing_member is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email already belongs to a member of your school.",
        )

    generated_password = payload.password or secrets.token_urlsafe(8)
    user = ctx.db.query(User).filter(User.email == email).first()
    if user is None:
        from ..core.security import hash_password

        user = User(
            email=email,
            hashed_password=hash_password(generated_password),
            full_name=payload.full_name.strip(),
            phone=payload.phone,
        )
        ctx.db.add(user)
        ctx.db.commit()
        ctx.db.refresh(user)

    member = OrganizationMember(
        organization_id=ctx.org_id,
        user_id=user.id,
        role=payload.role,
        invited_by_id=ctx.user.id,
    )
    ctx.db.add(member)
    joining = None
    if payload.joining_date:
        try:
            joining = date_type.fromisoformat(payload.joining_date)
        except ValueError:
            joining = None
    profile = Teacher(
        organization_id=ctx.org_id,
        user_id=user.id,
        employee_id=_new_employee_id(ctx.db, ctx.org_id),
        designation=payload.designation.strip() or "Teacher",
        level=_teacher_level(payload.level),
        gender=payload.gender,
        qualification=payload.qualification,
        department=payload.department,
        joining_date=joining,
        status="active",
    )
    ctx.db.add(profile)
    valid_subjects = [
        row[0]
        for row in ctx.db.query(Subject.id).filter(
            Subject.organization_id == ctx.org_id, Subject.id.in_(payload.subject_ids or [])
        ).all()
    ]
    for subject_id in valid_subjects:
        ctx.db.add(
            TeacherSubject(organization_id=ctx.org_id, teacher_id=user.id, subject_id=subject_id)
        )
    ctx.db.commit()

    email_sent = False
    if payload.send_email:
        email_sent = mailer.send_teacher_credentials(
            user.email, user.full_name, user.email, generated_password, ctx.organization.name
        )
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": payload.role,
        "employee_id": profile.employee_id,
        "level": profile.level,
        "temporary_password": generated_password,
        "email_sent": email_sent,
        "mail_configured": mailer.mail_configured(),
    }


@router.get("/teachers/{user_id}")
def teacher_profile(user_id: int, ctx: OrgContext = Depends(get_org_context)):
    member = (
        ctx.db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == ctx.org_id, OrganizationMember.user_id == user_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")
    user = ctx.db.get(User, user_id)
    profile = (
        ctx.db.query(Teacher)
        .filter(Teacher.organization_id == ctx.org_id, Teacher.user_id == user_id)
        .first()
    )
    subject_ids = [
        row[0]
        for row in ctx.db.query(TeacherSubject.subject_id).filter(
            TeacherSubject.organization_id == ctx.org_id, TeacherSubject.teacher_id == user_id
        ).all()
    ]
    assignments = (
        ctx.db.query(TeacherSubjectAssignment)
        .filter(
            TeacherSubjectAssignment.organization_id == ctx.org_id,
            TeacherSubjectAssignment.teacher_id == user_id,
        )
        .all()
    )
    return {
        "user_id": user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": member.role,
        "is_active": member.is_active,
        "employee_id": profile.employee_id if profile else None,
        "designation": profile.designation if profile else None,
        "level": profile.level if profile else None,
        "department": profile.department if profile else None,
        "qualification": profile.qualification if profile else None,
        "gender": profile.gender if profile else None,
        "status": profile.status if profile else "active",
        "joining_date": profile.joining_date.isoformat() if profile and profile.joining_date else None,
        "subject_ids": subject_ids,
        "assignments": _assignment_rows(ctx.db, ctx, assignments),
    }


@router.patch("/teachers/{user_id}")
def update_teacher(
    user_id: int, payload: TeacherUpdateRequest, ctx: OrgContext = Depends(get_org_context)
):
    _require_manager(ctx)
    member = (
        ctx.db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == ctx.org_id, OrganizationMember.user_id == user_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")
    if user_id == ctx.user.id and (payload.is_active is not None or payload.role is not None):
        raise HTTPException(status_code=400, detail="You cannot change your own role or status.")
    user = ctx.db.get(User, user_id)
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.role is not None:
        ensure_valid_role(payload.role)
        member.role = payload.role
    if payload.is_active is not None:
        member.is_active = payload.is_active
    profile = (
        ctx.db.query(Teacher)
        .filter(Teacher.organization_id == ctx.org_id, Teacher.user_id == user_id)
        .first()
    )
    if profile is not None:
        for field in ("designation", "qualification", "department", "gender", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(profile, field, value)
        if payload.level is not None:
            # An empty selection clears it again: the teacher then covers both levels.
            profile.level = _teacher_level(payload.level)
        if payload.joining_date is not None:
            try:
                profile.joining_date = date_type.fromisoformat(payload.joining_date)
            except ValueError:
                pass
    ctx.db.commit()
    return {"user_id": user_id, "full_name": user.full_name, "role": member.role, "is_active": member.is_active}


@router.put("/teachers/{user_id}/subjects")
def set_teacher_subjects(
    user_id: int, payload: TeacherSubjectsUpdate, ctx: OrgContext = Depends(get_org_context)
):
    _require_manager(ctx)
    ctx.db.query(TeacherSubject).filter(
        TeacherSubject.organization_id == ctx.org_id, TeacherSubject.teacher_id == user_id
    ).delete()
    valid = [
        row[0]
        for row in ctx.db.query(Subject.id).filter(
            Subject.organization_id == ctx.org_id, Subject.id.in_(payload.subject_ids or [])
        ).all()
    ]
    for subject_id in valid:
        ctx.db.add(
            TeacherSubject(organization_id=ctx.org_id, teacher_id=user_id, subject_id=subject_id)
        )
    ctx.db.commit()
    return {"user_id": user_id, "subject_ids": valid}


# ------------------------------------------------------------------
# Guardians / parents
# ------------------------------------------------------------------


@router.get("/guardians")
def list_guardians(ctx: OrgContext = Depends(get_org_context)):
    guardians = (
        ctx.db.query(Guardian)
        .filter(Guardian.organization_id == ctx.org_id)
        .order_by(Guardian.full_name.asc())
        .all()
    )
    links = (
        ctx.db.query(StudentGuardian, Student)
        .join(Student, Student.id == StudentGuardian.student_id)
        .filter(StudentGuardian.guardian_id.in_([g.id for g in guardians] or [0]))
        .all()
    )
    children: dict[int, list[dict]] = {}
    for link, student in links:
        children.setdefault(link.guardian_id, []).append(
            {"id": student.id, "name": student.name, "relationship": link.relationship}
        )
    return [
        {
            "id": g.id,
            "full_name": g.full_name,
            "phone": g.phone,
            "email": g.email,
            "children": children.get(g.id, []),
        }
        for g in guardians
    ]


@router.post("/guardians")
def create_guardian(payload: GuardianCreate, ctx: OrgContext = Depends(get_org_context)):
    _require_manager(ctx)
    guardian = Guardian(
        organization_id=ctx.org_id,
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        email=payload.email,
    )
    ctx.db.add(guardian)
    ctx.db.commit()
    ctx.db.refresh(guardian)
    return {"id": guardian.id, "full_name": guardian.full_name, "phone": guardian.phone, "email": guardian.email, "children": []}


@router.patch("/guardians/{guardian_id}")
def update_guardian(
    guardian_id: int, payload: GuardianUpdate, ctx: OrgContext = Depends(get_org_context)
):
    """Correct a guardian's name or contact details. A null phone/email clears it."""
    _require_manager(ctx)
    guardian = (
        ctx.db.query(Guardian)
        .filter(Guardian.id == guardian_id, Guardian.organization_id == ctx.org_id)
        .first()
    )
    if guardian is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found.")
    if payload.full_name is not None:
        guardian.full_name = payload.full_name.strip()
    provided = payload.model_fields_set
    for field in ("phone", "email"):
        if field in provided:
            value = getattr(payload, field)
            setattr(guardian, field, value.strip() if value else None)
    ctx.db.commit()
    return {
        "id": guardian.id,
        "full_name": guardian.full_name,
        "phone": guardian.phone,
        "email": guardian.email,
    }


@router.delete("/guardians/{guardian_id}")
def delete_guardian(guardian_id: int, ctx: OrgContext = Depends(get_org_context)):
    """Remove a guardian from the directory once no child is linked to them."""
    _require_manager(ctx)
    guardian = (
        ctx.db.query(Guardian)
        .filter(Guardian.id == guardian_id, Guardian.organization_id == ctx.org_id)
        .first()
    )
    if guardian is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found.")
    linked = (
        ctx.db.query(StudentGuardian)
        .filter(StudentGuardian.guardian_id == guardian_id)
        .count()
    )
    if linked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{guardian.full_name} is still linked to {linked} "
                f"student{'s' if linked != 1 else ''}. Unlink them first."
            ),
        )
    ctx.db.delete(guardian)
    ctx.db.commit()
    return {"status": "deleted"}


@router.post("/students/{student_id}/guardians")
def link_guardian(
    student_id: int, payload: StudentGuardianLink, ctx: OrgContext = Depends(get_org_context)
):
    _require_manager(ctx)
    student = (
        ctx.db.query(Student)
        .filter(Student.id == student_id, Student.organization_id == ctx.org_id)
        .first()
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    guardian = None
    if payload.guardian_id:
        guardian = (
            ctx.db.query(Guardian)
            .filter(Guardian.id == payload.guardian_id, Guardian.organization_id == ctx.org_id)
            .first()
        )
        if guardian is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found.")
    elif payload.full_name and payload.full_name.strip():
        guardian = Guardian(
            organization_id=ctx.org_id,
            full_name=payload.full_name.strip(),
            phone=payload.phone,
            email=payload.email,
        )
        ctx.db.add(guardian)
        ctx.db.commit()
        ctx.db.refresh(guardian)
    else:
        raise HTTPException(status_code=400, detail="Provide a guardian_id or a full_name.")
    existing = (
        ctx.db.query(StudentGuardian)
        .filter(StudentGuardian.student_id == student_id, StudentGuardian.guardian_id == guardian.id)
        .first()
    )
    if existing is None:
        ctx.db.add(
            StudentGuardian(
                student_id=student_id, guardian_id=guardian.id, relationship=payload.relationship
            )
        )
    ctx.db.commit()
    return {"guardian_id": guardian.id, "full_name": guardian.full_name, "relationship": payload.relationship}


@router.delete("/students/{student_id}/guardians/{guardian_id}")
def unlink_guardian(
    student_id: int, guardian_id: int, ctx: OrgContext = Depends(get_org_context)
):
    _require_manager(ctx)
    link = (
        ctx.db.query(StudentGuardian)
        .filter(StudentGuardian.student_id == student_id, StudentGuardian.guardian_id == guardian_id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")
    ctx.db.delete(link)
    ctx.db.commit()
    return {"status": "unlinked"}


# ------------------------------------------------------------------
# Student profile
# ------------------------------------------------------------------


@router.get("/students/{student_id}")
def student_profile(student_id: int, ctx: OrgContext = Depends(get_org_context)):
    student = (
        ctx.db.query(Student)
        .filter(Student.id == student_id, Student.organization_id == ctx.org_id)
        .first()
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    school_class = ctx.db.get(SchoolClass, student.class_id)
    section = ctx.db.get(Section, student.section_id) if student.section_id else None
    guardian_links = (
        ctx.db.query(StudentGuardian, Guardian)
        .join(Guardian, Guardian.id == StudentGuardian.guardian_id)
        .filter(StudentGuardian.student_id == student_id)
        .all()
    )
    attendance = (
        ctx.db.query(StudentAttendance)
        .filter(StudentAttendance.student_id == student_id)
        .all()
    )
    att_counts = {"present": 0, "absent": 0, "leave": 0, "late": 0}
    for row in attendance:
        att_counts[row.status] = att_counts.get(row.status, 0) + 1
    results = (
        ctx.db.query(MarksheetEntry, Marksheet)
        .join(Marksheet, Marksheet.id == MarksheetEntry.marksheet_id)
        .filter(MarksheetEntry.student_id == student_id)
        .order_by(Marksheet.created_at.desc())
        .limit(8)
        .all()
    )
    subject_names = {
        s.id: s.name for s in ctx.db.query(Subject).filter(Subject.organization_id == ctx.org_id).all()
    }
    return {
        "id": student.id,
        "name": student.name,
        "roll_no": student.roll_no,
        "class_id": student.class_id,
        "class": school_class.name if school_class else "",
        "section_id": student.section_id,
        "section": section.name if section else None,
        "is_active": student.is_active,
        "guardian_name": student.guardian_name,
        "guardian_phone": student.guardian_phone,
        "guardians": [
            {
                "id": g.id,
                "full_name": g.full_name,
                "phone": g.phone,
                "email": g.email,
                "relationship": link.relationship,
            }
            for link, g in guardian_links
        ],
        "attendance": att_counts,
        "results": [
            {
                "title": m.title,
                "subject": subject_names.get(m.subject_id, ""),
                "obtained": entry.obtained_marks,
                "total": entry.total_marks,
                "remarks": entry.remarks,
            }
            for entry, m in results
        ],
    }
