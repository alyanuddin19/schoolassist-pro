"""Marksheet upload/import and management."""

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from ..deps import OrgContext, get_org_context
from ..models import Marksheet, MarksheetEntry, SchoolClass, Section, Student, Subject, Test
from ..schemas import MarksheetManualRequest
from ..services import analytics
from ..services.access import ensure_teacher_can_access

router = APIRouter(prefix="/marksheets", tags=["marksheets"])


def _sheet_summary(db, ctx: OrgContext, sheet: Marksheet, include_entries: bool = False) -> dict:
    school_class = db.get(SchoolClass, sheet.class_id)
    subject = db.get(Subject, sheet.subject_id)
    section = db.get(Section, sheet.section_id) if sheet.section_id else None
    result = {
        "id": sheet.id,
        "title": sheet.title,
        "class_id": sheet.class_id,
        "class": school_class.name if school_class else "",
        "section": section.name if section else None,
        "subject_id": sheet.subject_id,
        "subject": subject.name if subject else "",
        "test_id": sheet.test_id,
        "exam_type": sheet.exam_type,
        "total_marks": sheet.total_marks,
        "source_file_name": sheet.source_file_name,
        "created_at": sheet.created_at.isoformat() if sheet.created_at else None,
    }
    if include_entries:
        entries = (
            db.query(MarksheetEntry)
            .filter(MarksheetEntry.marksheet_id == sheet.id)
            .order_by(MarksheetEntry.obtained_marks.desc())
            .all()
        )
        result["stats"] = analytics._stats_from_entries(entries)
        result["entries"] = [
            {
                "student_id": e.student_id,
                "roll_no": e.student.roll_no if e.student else "",
                "name": e.student.name if e.student else "",
                "obtained_marks": e.obtained_marks,
                "total_marks": e.total_marks,
                "percent": analytics._entry_percent(e),
                "grade": analytics.grade_for_percentage(analytics._entry_percent(e)),
                "remarks": e.remarks,
            }
            for e in entries
        ]
    return result


def _resolve_targets(ctx: OrgContext, class_id: int, subject_id: int, section_id: int | None):
    school_class = (
        ctx.db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    subject = (
        ctx.db.query(Subject)
        .filter(Subject.id == subject_id, Subject.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None or subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class or subject not found."
        )
    ensure_teacher_can_access(ctx.db, ctx, class_id, subject_id)
    return school_class, subject


def _store_entries(
    ctx: OrgContext,
    sheet: Marksheet,
    rows: list[tuple[int, float, str | None]],
):
    for student_id, obtained, remarks in rows:
        ctx.db.add(
            MarksheetEntry(
                organization_id=ctx.org_id,
                marksheet_id=sheet.id,
                student_id=student_id,
                obtained_marks=obtained,
                total_marks=sheet.total_marks,
                remarks=remarks,
            )
        )
    ctx.db.commit()


@router.post("/upload")
async def upload_marksheet(
    file: UploadFile = File(...),
    class_id: int = Form(...),
    subject_id: int = Form(...),
    section_id: int | None = Form(default=None),
    test_id: int | None = Form(default=None),
    title: str = Form(default=""),
    exam_type: str = Form(default=""),
    total_marks: float = Form(default=100),
    ctx: OrgContext = Depends(get_org_context),
):
    """Import a marksheet from Excel/CSV.

    Expected columns (any order, names matched loosely):
    roll_no / roll number, name (optional), marks / obtained marks, remarks (optional).
    Students are matched by roll number within the selected class.
    """
    school_class, subject = _resolve_targets(ctx, class_id, subject_id, section_id)

    content = await file.read()
    try:
        if (file.filename or "").lower().endswith(".csv"):
            frame = pd.read_csv(io.BytesIO(content))
        else:
            frame = pd.read_excel(io.BytesIO(content))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the file. Upload .xlsx or .csv with columns: roll_no, marks.",
        )

    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    roll_col = next((c for c in frame.columns if "roll" in c), None)
    marks_col = next(
        (c for c in frame.columns if "mark" in c and "total" not in c), None
    )
    remarks_col = next((c for c in frame.columns if "remark" in c), None)
    if roll_col is None or marks_col is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must include a roll number column and a marks column.",
        )

    students = (
        ctx.db.query(Student)
        .filter(
            Student.organization_id == ctx.org_id,
            Student.class_id == class_id,
            Student.is_active.is_(True),
        )
        .all()
    )
    by_roll = {str(s.roll_no).strip().upper(): s for s in students}

    matched: list[tuple[int, float, str | None]] = []
    unmatched: list[dict] = []
    for _, row in frame.iterrows():
        roll_no = str(row[roll_col]).strip()
        raw_marks = row[marks_col]
        try:
            obtained = float(raw_marks)
        except (TypeError, ValueError):
            continue
        student = by_roll.get(roll_no.upper())
        if student is None:
            unmatched.append(
                {"roll_no": roll_no, "marks": obtained}
            )
            continue
        remarks = str(row[remarks_col]).strip() if remarks_col else None
        matched.append((student.id, obtained, remarks if remarks and remarks.lower() != "nan" else None))

    if not matched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No students matched. Make sure roll numbers in the file match the "
                "students added in Setup for this class."
            ),
        )

    sheet = Marksheet(
        organization_id=ctx.org_id,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        test_id=test_id,
        title=title or f"{subject.name} - {school_class.name} Marksheet",
        exam_type=exam_type or None,
        total_marks=total_marks,
        uploaded_by_id=ctx.user.id,
        source_file_name=file.filename,
    )
    ctx.db.add(sheet)
    ctx.db.commit()
    ctx.db.refresh(sheet)

    _store_entries(ctx, sheet, matched)
    return {
        "marksheet": _sheet_summary(ctx.db, ctx, sheet, include_entries=True),
        "imported": len(matched),
        "unmatched": unmatched[:20],
    }


@router.post("")
def create_manual_marksheet(
    payload: MarksheetManualRequest, ctx: OrgContext = Depends(get_org_context)
):
    """Create a marksheet with manually typed entries."""
    school_class, subject = _resolve_targets(
        ctx, payload.class_id, payload.subject_id, payload.section_id
    )
    sheet = Marksheet(
        organization_id=ctx.org_id,
        class_id=payload.class_id,
        section_id=payload.section_id,
        subject_id=payload.subject_id,
        test_id=payload.test_id,
        title=payload.title,
        exam_type=payload.exam_type,
        total_marks=payload.total_marks,
        uploaded_by_id=ctx.user.id,
    )
    ctx.db.add(sheet)
    ctx.db.commit()
    ctx.db.refresh(sheet)

    rows = [(e.student_id, e.obtained_marks, e.remarks) for e in payload.entries]
    _store_entries(ctx, sheet, rows)
    return _sheet_summary(ctx.db, ctx, sheet, include_entries=True)


@router.get("")
def list_marksheets(
    class_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    query = ctx.db.query(Marksheet).filter(Marksheet.organization_id == ctx.org_id)
    if class_id:
        query = query.filter(Marksheet.class_id == class_id)
    if subject_id:
        query = query.filter(Marksheet.subject_id == subject_id)
    sheets = query.order_by(Marksheet.created_at.desc()).limit(100).all()
    return [_sheet_summary(ctx.db, ctx, sheet) for sheet in sheets]


@router.get("/{marksheet_id}")
def get_marksheet(marksheet_id: int, ctx: OrgContext = Depends(get_org_context)):
    sheet = (
        ctx.db.query(Marksheet)
        .filter(Marksheet.id == marksheet_id, Marksheet.organization_id == ctx.org_id)
        .first()
    )
    if sheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marksheet not found.")
    return _sheet_summary(ctx.db, ctx, sheet, include_entries=True)


@router.delete("/{marksheet_id}")
def delete_marksheet(marksheet_id: int, ctx: OrgContext = Depends(get_org_context)):
    sheet = (
        ctx.db.query(Marksheet)
        .filter(Marksheet.id == marksheet_id, Marksheet.organization_id == ctx.org_id)
        .first()
    )
    if sheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marksheet not found.")
    ctx.db.delete(sheet)
    ctx.db.commit()
    return {"status": "deleted"}
