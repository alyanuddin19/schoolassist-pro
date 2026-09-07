"""Export endpoints: worksheets, tests, marksheets and reports as PDF/DOCX/Excel."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..deps import OrgContext, get_org_context
from ..models import Marksheet, MarksheetEntry, Report, SchoolClass, Subject, Test, Worksheet
from ..services import analytics
from ..services.exporters import build_docx, build_pdf, build_xlsx

router = APIRouter(prefix="/exports", tags=["exports"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _file_response(buffer, filename: str, file_format: str) -> StreamingResponse:
    return StreamingResponse(
        buffer,
        media_type=MEDIA_TYPES[file_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _document_export(ctx: OrgContext, title: str, body: str, subtitle: str, filename: str, file_format: str):
    if file_format == "docx":
        return _file_response(build_docx(title, body, subtitle), filename, "docx")
    return _file_response(build_pdf(title, body, subtitle), filename, "pdf")


@router.get("/worksheet/{worksheet_id}")
def export_worksheet(
    worksheet_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|docx)$"),
    ctx: OrgContext = Depends(get_org_context),
):
    worksheet = (
        ctx.db.query(Worksheet)
        .filter(Worksheet.id == worksheet_id, Worksheet.organization_id == ctx.org_id)
        .first()
    )
    if worksheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worksheet not found.")

    school_class = ctx.db.get(SchoolClass, worksheet.class_id)
    subject = ctx.db.get(Subject, worksheet.subject_id)
    subtitle = (
        f"{ctx.organization.name} | {school_class.name if school_class else ''} - "
        f"{subject.name if subject else ''}"
    )
    body = "\n".join(
        part
        for part in [
            worksheet.content,
            "\n\n===== ANSWER KEY =====\n" + worksheet.answer_key if worksheet.answer_key else "",
            "\n\n===== MARKING SCHEME =====\n" + worksheet.marking_scheme
            if worksheet.marking_scheme
            else "",
        ]
        if part
    )
    return _document_export(
        ctx, worksheet.title, body, subtitle, f"worksheet-{worksheet.id}.{format}", format
    )


@router.get("/test/{test_id}")
def export_test(
    test_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|docx)$"),
    ctx: OrgContext = Depends(get_org_context),
):
    test = (
        ctx.db.query(Test)
        .filter(Test.id == test_id, Test.organization_id == ctx.org_id)
        .first()
    )
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found.")

    school_class = ctx.db.get(SchoolClass, test.class_id)
    subject = ctx.db.get(Subject, test.subject_id)
    subtitle = (
        f"{ctx.organization.name} | {school_class.name if school_class else ''} - "
        f"{subject.name if subject else ''} | Total marks: {test.total_marks or '-'}"
    )
    body = "\n".join(
        part
        for part in [
            test.content,
            "\n\n===== ANSWER KEY =====\n" + test.answer_key if test.answer_key else "",
            "\n\n===== MARKING SCHEME =====\n" + test.marking_scheme if test.marking_scheme else "",
        ]
        if part
    )
    return _document_export(ctx, test.title, body, subtitle, f"test-{test.id}.{format}", format)


@router.get("/marksheet/{marksheet_id}")
def export_marksheet(
    marksheet_id: int,
    format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"),
    ctx: OrgContext = Depends(get_org_context),
):
    sheet = (
        ctx.db.query(Marksheet)
        .filter(Marksheet.id == marksheet_id, Marksheet.organization_id == ctx.org_id)
        .first()
    )
    if sheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marksheet not found.")

    entries = (
        ctx.db.query(MarksheetEntry)
        .filter(MarksheetEntry.marksheet_id == sheet.id)
        .order_by(MarksheetEntry.obtained_marks.desc())
        .all()
    )
    rows = [
        {
            "Roll No": e.student.roll_no if e.student else "",
            "Student": e.student.name if e.student else "",
            "Obtained": e.obtained_marks,
            "Total": e.total_marks,
            "Percent": analytics._entry_percent(e),
            "Grade": analytics.grade_for_percentage(analytics._entry_percent(e)),
            "Remarks": e.remarks or "",
        }
        for e in entries
    ]

    if format == "xlsx":
        columns = ["Roll No", "Student", "Obtained", "Total", "Percent", "Grade", "Remarks"]
        return _file_response(
            build_xlsx(sheet.title[:30], columns, rows), f"marksheet-{sheet.id}.xlsx", "xlsx"
        )

    body_lines = [
        f"Class: {ctx.db.get(SchoolClass, sheet.class_id).name if sheet.class_id else ''}",
        f"Subject: {ctx.db.get(Subject, sheet.subject_id).name if sheet.subject_id else ''}",
        f"Total marks: {sheet.total_marks}",
        "",
    ]
    for row in rows:
        body_lines.append(
            f"{row['Roll No']} - {row['Student']}: {row['Obtained']}/{row['Total']} "
            f"({row['Percent']}%) Grade {row['Grade']}"
        )
    stats = analytics._stats_from_entries(entries)
    body_lines += [
        "",
        f"Average: {stats['average']} | Highest: {stats['highest']} | "
        f"Lowest: {stats['lowest']} | Pass rate: {stats['pass_rate']}%",
    ]
    return _document_export(
        ctx, sheet.title, "\n".join(body_lines), ctx.organization.name, f"marksheet-{sheet.id}.pdf", "pdf"
    )


@router.get("/report/{report_id}")
def export_report(
    report_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|docx|xlsx)$"),
    ctx: OrgContext = Depends(get_org_context),
):
    report = (
        ctx.db.query(Report)
        .filter(Report.id == report_id, Report.organization_id == ctx.org_id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    content = report.content or {}

    if format == "xlsx" and report.report_type == "final_term":
        columns = ["Roll No", "Name", "Section", *content.get("subject_order", []), "Overall %", "Grade", "Status"]
        rows = [
            {
                "Roll No": s["roll_no"],
                "Name": s["name"],
                "Section": s.get("section", ""),
                **{subject: value for subject, value in s.get("subjects", {}).items()},
                "Overall %": s["overall_percent"],
                "Grade": s["grade"],
                "Status": s["status"],
            }
            for s in content.get("students", [])
        ]
        return _file_response(
            build_xlsx(report.title[:30], columns, rows), f"report-{report.id}.xlsx", "xlsx"
        )

    lines: list[str] = []
    if report.report_type == "final_term":
        lines.append(f"Class: {content.get('class', '')}")
        lines.append(f"Class average: {content.get('class_average', 0)}%")
        lines.append(f"Marksheets included: {content.get('marksheets_included', 0)}")
        lines.append("")
        header = (
            f"{'Roll No':<10} {'Name':<22} {'Overall %':<10} {'Grade':<6} Status"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for student in content.get("students", []):
            lines.append(
                f"{student['roll_no']:<10} {student['name']:<22} "
                f"{student['overall_percent']:<10} {student['grade']:<6} {student['status']}"
            )
        lines.append("")
        lines.append("Subject averages:")
        for stat in content.get("subject_stats", []):
            lines.append(
                f"  {stat['subject']}: average {stat['average']}% "
                f"(highest {stat['highest']}%, lowest {stat['lowest']}%)"
            )
    else:
        lines.append(str(content))

    return _document_export(
        ctx, report.title, "\n".join(lines), ctx.organization.name, f"report-{report.id}.{format}", format
    )
