"""Performance analytics: marks, averages, weak students and final term reports."""

from sqlalchemy.orm import Session

from ..models import (
    Marksheet,
    MarksheetEntry,
    REPORT_TYPE_FINAL_TERM,
    Report,
    SchoolClass,
    Section,
    Student,
    Subject,
)

# Schools in Pakistan commonly use 40% as the pass mark (33% in boards)
DEFAULT_PASS_PERCENT = 40.0


def grade_for_percentage(percent: float) -> str:
    if percent >= 90:
        return "A+"
    if percent >= 80:
        return "A"
    if percent >= 70:
        return "B"
    if percent >= 60:
        return "C"
    if percent >= 50:
        return "D"
    if percent >= 40:
        return "E"
    return "F"


def _entry_percent(entry: MarksheetEntry) -> float:
    total = entry.total_marks or 0
    if total <= 0:
        return 0.0
    return round((entry.obtained_marks or 0) / total * 100, 1)


def _stats_from_entries(entries: list[MarksheetEntry]) -> dict:
    if not entries:
        return {
            "count": 0,
            "average": 0,
            "highest": 0,
            "lowest": 0,
            "pass_rate": 0,
            "average_percent": 0,
        }
    percents = [_entry_percent(e) for e in entries]
    obtained = [e.obtained_marks or 0 for e in entries]
    pass_count = sum(1 for p in percents if p >= DEFAULT_PASS_PERCENT)
    return {
        "count": len(entries),
        "average": round(sum(obtained) / len(obtained), 1),
        "highest": max(obtained),
        "lowest": min(obtained),
        "pass_rate": round(pass_count / len(entries) * 100, 1),
        "average_percent": round(sum(percents) / len(percents), 1),
    }


def _base_marksheet_query(db: Session, organization_id: int, class_id: int | None = None):
    query = db.query(Marksheet).filter(Marksheet.organization_id == organization_id)
    if class_id is not None:
        query = query.filter(Marksheet.class_id == class_id)
    return query


def subject_performance(
    db: Session,
    organization_id: int,
    class_id: int,
    subject_id: int,
    section_id: int | None = None,
    threshold_percent: float = DEFAULT_PASS_PERCENT,
) -> dict:
    query = _base_marksheet_query(db, organization_id, class_id).filter(
        Marksheet.subject_id == subject_id
    )
    if section_id is not None:
        query = query.filter(Marksheet.section_id == section_id)
    marksheets = query.order_by(Marksheet.created_at.desc()).all()

    rows: list[dict] = []
    for sheet in marksheets:
        entries = (
            db.query(MarksheetEntry)
            .filter(MarksheetEntry.marksheet_id == sheet.id)
            .all()
        )
        stats = _stats_from_entries(entries)
        weak = [
            {
                "student_id": e.student_id,
                "student_name": e.student.name if e.student else "",
                "roll_no": e.student.roll_no if e.student else "",
                "obtained": e.obtained_marks,
                "total": e.total_marks,
                "percent": _entry_percent(e),
            }
            for e in entries
            if _entry_percent(e) < threshold_percent
        ]
        rows.append(
            {
                "marksheet_id": sheet.id,
                "title": sheet.title,
                "exam_type": sheet.exam_type,
                "total_marks": sheet.total_marks,
                "created_at": sheet.created_at.isoformat() if sheet.created_at else None,
                "stats": stats,
                "weak_students": sorted(weak, key=lambda w: w["percent"]),
            }
        )
    return {"marksheets": rows}


def class_report(
    db: Session,
    organization_id: int,
    class_id: int,
    section_id: int | None = None,
) -> dict:
    """Subject-wise class report (each subject averaged across all its marksheets)."""
    query = _base_marksheet_query(db, organization_id, class_id)
    if section_id is not None:
        query = query.filter(Marksheet.section_id == section_id)
    marksheets = query.all()
    if not marksheets:
        return {"subjects": []}

    by_subject: dict[int, list[Marksheet]] = {}
    for sheet in marksheets:
        by_subject.setdefault(sheet.subject_id, []).append(sheet)

    subjects = []
    for subject_id, sheets in by_subject.items():
        subject = db.get(Subject, subject_id)
        all_entries: list[MarksheetEntry] = []
        for sheet in sheets:
            all_entries.extend(
                db.query(MarksheetEntry).filter(MarksheetEntry.marksheet_id == sheet.id).all()
            )
        stats = _stats_from_entries(all_entries)
        subjects.append(
            {
                "subject_id": subject_id,
                "subject_name": subject.name if subject else "Unknown",
                "marksheets": len(sheets),
                "stats": stats,
            }
        )
    subjects.sort(key=lambda s: s["subject_name"])
    return {"subjects": subjects}


def student_performance(db: Session, organization_id: int, student_id: int) -> dict:
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.organization_id == organization_id)
        .first()
    )
    if student is None:
        return {}

    entries = (
        db.query(MarksheetEntry)
        .join(Marksheet, Marksheet.id == MarksheetEntry.marksheet_id)
        .filter(
            MarksheetEntry.student_id == student_id,
            MarksheetEntry.organization_id == organization_id,
        )
        .order_by(Marksheet.created_at.desc())
        .all()
    )

    by_subject: dict[int, list] = {}
    for entry in entries:
        sheet = entry.marksheet
        by_subject.setdefault(sheet.subject_id, []).append(entry)

    subject_rows = []
    all_percents: list[float] = []
    for subject_id, subject_entries in by_subject.items():
        subject = db.get(Subject, subject_id)
        percents = [_entry_percent(e) for e in subject_entries]
        all_percents.extend(percents)
        subject_rows.append(
            {
                "subject_id": subject_id,
                "subject_name": subject.name if subject else "Unknown",
                "assessments": len(subject_entries),
                "average_percent": round(sum(percents) / len(percents), 1),
                "latest_percent": percents[0],
                "grade": grade_for_percentage(sum(percents) / len(percents)),
                "details": [
                    {
                        "title": e.marksheet.title,
                        "exam_type": e.marksheet.exam_type,
                        "obtained": e.obtained_marks,
                        "total": e.total_marks,
                        "percent": _entry_percent(e),
                    }
                    for e in subject_entries
                ],
            }
        )
    subject_rows.sort(key=lambda r: r["subject_name"])

    overall = round(sum(all_percents) / len(all_percents), 1) if all_percents else 0
    school_class = db.get(SchoolClass, student.class_id)
    section = db.get(Section, student.section_id) if student.section_id else None

    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "roll_no": student.roll_no,
            "class": school_class.name if school_class else "",
            "section": section.name if section else None,
        },
        "subjects": subject_rows,
        "overall_percent": overall,
        "overall_grade": grade_for_percentage(overall),
        "assessment_count": len(entries),
    }


def weak_students(
    db: Session,
    organization_id: int,
    class_id: int,
    subject_id: int | None = None,
    section_id: int | None = None,
    threshold_percent: float = DEFAULT_PASS_PERCENT,
) -> dict:
    """Students whose average is below the threshold in a subject (or all subjects)."""
    query = _base_marksheet_query(db, organization_id, class_id)
    if subject_id is not None:
        query = query.filter(Marksheet.subject_id == subject_id)
    if section_id is not None:
        query = query.filter(Marksheet.section_id == section_id)
    marksheets = query.all()
    if not marksheets:
        return {"threshold_percent": threshold_percent, "students": []}

    per_student: dict[int, list] = {}
    for sheet in marksheets:
        entries = (
            db.query(MarksheetEntry)
            .filter(MarksheetEntry.marksheet_id == sheet.id)
            .all()
        )
        for entry in entries:
            per_student.setdefault(entry.student_id, []).append(entry)

    weak = []
    for student_id, student_entries in per_student.items():
        student = student_entries[0].student
        percents = [_entry_percent(e) for e in student_entries]
        avg = sum(percents) / len(percents)
        if avg < threshold_percent:
            weak.append(
                {
                    "student_id": student_id,
                    "student_name": student.name if student else "",
                    "roll_no": student.roll_no if student else "",
                    "average_percent": round(avg, 1),
                    "assessments": len(student_entries),
                    "grade": grade_for_percentage(avg),
                }
            )
    weak.sort(key=lambda s: s["average_percent"])
    return {"threshold_percent": threshold_percent, "students": weak}


def build_final_term_report(
    db: Session,
    organization_id: int,
    class_id: int,
    section_id: int | None = None,
    generated_by_id: int = 0,
    title: str | None = None,
    academic_year: str | None = None,
) -> Report:
    """Combine all marksheets of a class into a final term result report."""
    school_class = db.get(SchoolClass, class_id)
    class_name = school_class.name if school_class else "Class"

    query = _base_marksheet_query(db, organization_id, class_id)
    if section_id is not None:
        query = query.filter(Marksheet.section_id == section_id)
    marksheets = query.all()

    subjects = sorted({s.subject_id for s in marksheets})
    subject_names = {}
    for sid in subjects:
        subject = db.get(Subject, sid)
        subject_names[sid] = subject.name if subject else f"Subject {sid}"

    # Collect per-student totals per subject (average percent across assessments)
    student_ids = {
        e.student_id
        for sheet in marksheets
        for e in db.query(MarksheetEntry)
        .filter(MarksheetEntry.marksheet_id == sheet.id)
        .all()
    }
    students = db.query(Student).filter(Student.id.in_(student_ids)).all() if student_ids else []
    students.sort(key=lambda s: (s.section_id or 0, s.roll_no))

    student_rows = []
    for student in students:
        entries = (
            db.query(MarksheetEntry)
            .join(Marksheet, Marksheet.id == MarksheetEntry.marksheet_id)
            .filter(
                MarksheetEntry.student_id == student.id,
                Marksheet.organization_id == organization_id,
                Marksheet.class_id == class_id,
            )
            .all()
        )
        subject_scores: dict[int, list] = {}
        for entry in entries:
            subject_scores.setdefault(entry.marksheet.subject_id, []).append(_entry_percent(entry))

        row = {
            "student_id": student.id,
            "name": student.name,
            "roll_no": student.roll_no,
            "section": (db.get(Section, student.section_id).name if student.section_id else ""),
            "subjects": {},
        }
        percents: list[float] = []
        for sid in subjects:
            scores = subject_scores.get(sid, [])
            value = round(sum(scores) / len(scores), 1) if scores else None
            row["subjects"][subject_names[sid]] = value
            if value is not None:
                percents.append(value)
        overall = round(sum(percents) / len(percents), 1) if percents else 0
        row["overall_percent"] = overall
        row["grade"] = grade_for_percentage(overall)
        row["status"] = "Pass" if overall >= DEFAULT_PASS_PERCENT else "Needs Support"
        student_rows.append(row)

    subject_stats = []
    for sid in subjects:
        values = [r["subjects"][subject_names[sid]] for r in student_rows if r["subjects"].get(subject_names[sid]) is not None]
        if values:
            subject_stats.append(
                {
                    "subject": subject_names[sid],
                    "average": round(sum(values) / len(values), 1),
                    "highest": max(values),
                    "lowest": min(values),
                }
            )

    class_average = (
        round(sum(r["overall_percent"] for r in student_rows) / len(student_rows), 1)
        if student_rows
        else 0
    )
    content = {
        "class": class_name,
        "subject_order": [subject_names[sid] for sid in subjects],
        "students": student_rows,
        "subject_stats": subject_stats,
        "class_average": class_average,
        "pass_percent": DEFAULT_PASS_PERCENT,
        "marksheets_included": len(marksheets),
    }

    report = Report(
        organization_id=organization_id,
        report_type=REPORT_TYPE_FINAL_TERM,
        class_id=class_id,
        section_id=section_id,
        academic_year=academic_year,
        title=title or f"Final Term Report - {class_name}",
        content=content,
        generated_by_id=generated_by_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
