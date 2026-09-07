"""Test paper generator endpoints (weekly, monthly, mid term, final term)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import OrgContext, get_org_context
from ..models import (
    ALL_TEST_TYPES,
    ROLE_ORG_ADMIN,
    SchoolClass,
    Section,
    Subject,
    Test,
    User,
)
from ..schemas import TestGenerateRequest
from ..services.content_service import create_test

router = APIRouter(prefix="/tests", tags=["tests"])


def _serialize(db, ctx: OrgContext, test: Test) -> dict:
    school_class = db.get(SchoolClass, test.class_id)
    subject = db.get(Subject, test.subject_id)
    section = db.get(Section, test.section_id) if test.section_id else None
    creator = db.get(User, test.created_by_id)
    return {
        "id": test.id,
        "title": test.title,
        "test_type": test.test_type,
        "topic": test.topic,
        "class_id": test.class_id,
        "class": school_class.name if school_class else "",
        "section": section.name if section else None,
        "subject_id": test.subject_id,
        "subject": subject.name if subject else "",
        "total_marks": test.total_marks,
        "duration_minutes": test.duration_minutes,
        "language": test.language,
        "content": test.content,
        "answer_key": test.answer_key,
        "marking_scheme": test.marking_scheme,
        "created_by": creator.full_name if creator else "",
        "created_at": test.created_at.isoformat() if test.created_at else None,
    }


@router.post("/generate")
def generate_test(payload: TestGenerateRequest, ctx: OrgContext = Depends(get_org_context)):
    if payload.test_type not in ALL_TEST_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"test_type must be one of {', '.join(ALL_TEST_TYPES)}",
        )
    try:
        test = create_test(ctx.db, ctx, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _serialize(ctx.db, ctx, test)


@router.get("")
def list_tests(
    class_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    test_type: str | None = Query(default=None),
    ctx: OrgContext = Depends(get_org_context),
):
    query = ctx.db.query(Test).filter(Test.organization_id == ctx.org_id)
    if class_id:
        query = query.filter(Test.class_id == class_id)
    if subject_id:
        query = query.filter(Test.subject_id == subject_id)
    if test_type:
        query = query.filter(Test.test_type == test_type)
    tests = query.order_by(Test.created_at.desc()).limit(100).all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "test_type": t.test_type,
            "topic": t.topic,
            "class": (ctx.db.get(SchoolClass, t.class_id).name if t.class_id else ""),
            "subject": (ctx.db.get(Subject, t.subject_id).name if t.subject_id else ""),
            "total_marks": t.total_marks,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tests
    ]


@router.get("/{test_id}")
def get_test(test_id: int, ctx: OrgContext = Depends(get_org_context)):
    test = (
        ctx.db.query(Test)
        .filter(Test.id == test_id, Test.organization_id == ctx.org_id)
        .first()
    )
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found.")
    return _serialize(ctx.db, ctx, test)


@router.delete("/{test_id}")
def delete_test(test_id: int, ctx: OrgContext = Depends(get_org_context)):
    test = (
        ctx.db.query(Test)
        .filter(Test.id == test_id, Test.organization_id == ctx.org_id)
        .first()
    )
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found.")
    if test.created_by_id != ctx.user.id and ctx.role != ROLE_ORG_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or the school owner can delete this test.",
        )
    ctx.db.delete(test)
    ctx.db.commit()
    return {"status": "deleted"}
