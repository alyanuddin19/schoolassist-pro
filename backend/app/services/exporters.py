"""Export builders: DOCX, PDF and Excel files for worksheets, tests and reports."""

import io

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _clean_line(line: str) -> str:
    return (line or "").replace("\r", "")


def build_docx(title: str, body: str, subtitle: str = "") -> io.BytesIO:
    doc = Document()
    doc.add_heading(title, level=1)
    if subtitle:
        doc.add_paragraph(subtitle)

    for line in (body or "").split("\n"):
        text = _clean_line(line).strip()
        if not text:
            continue
        if text.startswith("SECTION") or text.startswith("===") or text.isupper() and len(text) < 60:
            doc.add_heading(text, level=2)
        else:
            doc.add_paragraph(text)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _safe_pdf_text(text: str) -> str:
    # Escape XML entities for reportlab Paragraphs and keep line breaks
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(title: str, body: str, subtitle: str = "") -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    heading = ParagraphStyle("SaHeading", parent=styles["Title"], fontSize=16, spaceAfter=8)
    sub = ParagraphStyle("SaSub", parent=styles["Normal"], fontSize=10, spaceAfter=12)
    section_style = ParagraphStyle(
        "SaSection", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4
    )
    body_style = ParagraphStyle("SaBody", parent=styles["Normal"], fontSize=10, leading=14)

    story: list = [Paragraph(_safe_pdf_text(title), heading)]
    if subtitle:
        story.append(Paragraph(_safe_pdf_text(subtitle), sub))

    for line in (body or "").split("\n"):
        text = _clean_line(line).strip()
        if not text:
            continue
        if (
            text.upper().startswith("SECTION")
            or text.upper().startswith("===")
            or (text.isupper() and len(text) < 60)
        ):
            story.append(Paragraph(_safe_pdf_text(text), section_style))
        else:
            story.append(Paragraph(_safe_pdf_text(text), body_style))
        story.append(Spacer(1, 2))

    doc.build(story)
    buffer.seek(0)
    return buffer


def build_seating_pdf(title: str, subtitle: str, sections: list) -> io.BytesIO:
    """Class-wise seating plan PDF: one headed seat table per section.

    sections: [{"heading": str, "rows": [[roll no., student, room, seat no.], ...]}]
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    heading = ParagraphStyle("SaSeatTitle", parent=styles["Title"], fontSize=16, spaceAfter=6)
    sub = ParagraphStyle("SaSeatSub", parent=styles["Normal"], fontSize=10, spaceAfter=12)
    section_style = ParagraphStyle(
        "SaSeatSection", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=5
    )

    story: list = [Paragraph(_safe_pdf_text(title), heading)]
    if subtitle:
        story.append(Paragraph(_safe_pdf_text(subtitle), sub))

    for section in sections:
        story.append(Paragraph(_safe_pdf_text(section["heading"]), section_style))
        data = [["Roll no.", "Student", "Room", "Seat no."]]
        for row in section["rows"]:
            data.append([str(cell) for cell in row])
        table = Table(data, colWidths=[22 * mm, 72 * mm, 42 * mm, 22 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDFB")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C7D0EA")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def build_xlsx(sheet_title: str, columns: list, rows: list) -> io.BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (sheet_title or "Sheet")[:31]

    header_fill = PatternFill(start_color="1B7A43", end_color="1B7A43", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for col_index, column in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=col_index, value=column)
        cell.fill = header_fill
        cell.font = header_font
        sheet.column_dimensions[get_column_letter(col_index)].width = max(len(str(column)) + 4, 12)

    for row_index, row in enumerate(rows, start=2):
        for col_index, column in enumerate(columns, start=1):
            value = row.get(column)
            sheet.cell(row=row_index, column=col_index, value=value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
