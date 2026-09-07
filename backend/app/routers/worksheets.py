"""Worksheet generator endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import OrgContext, get_org_context
from ..models import ROLE_ORG_ADMIN, SchoolClass, Section, Subject, User, Worksheet
from ..schemas import WorksheetGenerateRequest
from ..services.content_service import create_worksheet

router = APIRouter(prefix="/worksheets", tags=["worksheets"])


def _serialize(db, ctx: OrgContext, worksheet: Worksheet) -> dict:
    school_class = db.get(SchoolClass, worksheet.class_id)
    subject = db.get(Subject, worksheet.subject_id)
    section = db.get(Section, worksheet.section_id) if worksheet.section_id else None
    creator = db.get(User, worksheet.created_by_id)
    return {
        "id": worksheet.id,
        "title": worksheet.title,
        "topic": worksheet.topic,
        "class_id": worksheet.class_id,
        "class": school_class.name if school_class else "",
        "section": section.name if section else None,
        "subject_id": worksheet.subject_id,
        "subject": subject.name if subject else "",
        "difficulty": worksheet.difficulty,
        "language": worksheet.language,
        "content": worksheet.content,
        "answer_key": worksheet.answer_key,
        "marking_scheme": worksheet.marking_scheme,
        "created_by": creator.full_name if creator else "",
        "created_at": worksheet.created_at.isoformat() if worksheet.created_at else None,
    }


@router.post("/generate")
def generate_worksheet(
    payload: WorksheetGenerateRequest, ctx: OrgContext = Depends(get_org_context)
):
    try:
        worksheet = create_worksheet(ctx.db, ctx, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _serialize(ctx.db, ctx, worksheet)


@router.get("")
def list_worksheets(
    class_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    query = ctx.db.query(Worksheet).filter(Worksheet.organization_id == ctx.org_id)
    if class_id:
        query = query.filter(Worksheet.class_id == class_id)
    if subject_id:
        query = query.filter(Worksheet.subject_id == subject_id)
    worksheets = query.order_by(Worksheet.created_at.desc()).limit(100).all()
    return [
        {
            "id": w.id,
            "title": w.title,
            "topic": w.topic,
            "class": (ctx.db.get(SchoolClass, w.class_id).name if w.class_id else ""),
            "subject": (ctx.db.get(Subject, w.subject_id).name if w.subject_id else ""),
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in worksheets
    ]


@router.get("/{worksheet_id}")
def get_worksheet(worksheet_id: int, ctx: OrgContext = Depends(get_org_context)):
    worksheet = (
        ctx.db.query(Worksheet)
        .filter(Worksheet.id == worksheet_id, Worksheet.organization_id == ctx.org_id)
        .first()
    )
    if worksheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worksheet not found.")
    return _serialize(ctx.db, ctx, worksheet)


@router.delete("/{worksheet_id}")
def delete_worksheet(worksheet_id: int, ctx: OrgContext = Depends(get_org_context)):
    worksheet = (
        ctx.db.query(Worksheet)
        .filter(Worksheet.id == worksheet_id, Worksheet.organization_id == ctx.org_id)
        .first()
    )
    if worksheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worksheet not found.")
    if worksheet.created_by_id != ctx.user.id and ctx.role != ROLE_ORG_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or the school owner can delete this worksheet.",
        )
    ctx.db.delete(worksheet)
    ctx.db.commit()
    return {"status": "deleted"}
