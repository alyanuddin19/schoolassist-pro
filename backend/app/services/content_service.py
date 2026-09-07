"""Shared content generation for worksheets and tests.

Used by both the REST endpoints and the AI assistant action handlers,
so the chatbot and the UI generate content through exactly the same
safe, permission-checked code path.
"""

from sqlalchemy.orm import Session

from ..deps import OrgContext
from ..models import SchoolClass, Section, Subject, Test, Worksheet
from ..schemas import QuestionCounts, TestGenerateRequest, WorksheetGenerateRequest
from .access import ensure_teacher_can_access
from .generation import build_test_prompt, build_worksheet_prompt, split_generated_sections
from .qwen_client import get_qwen_client


def _get_org_class(db: Session, ctx: OrgContext, class_id: int) -> SchoolClass:
    school_class = (
        db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.organization_id == ctx.org_id)
        .first()
    )
    if school_class is None:
        raise ValueError("Class not found in your school")
    return school_class


def _get_org_subject(db: Session, ctx: OrgContext, subject_id: int) -> Subject:
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.organization_id == ctx.org_id)
        .first()
    )
    if subject is None:
        raise ValueError("Subject not found in your school")
    return subject


def _get_org_section(db: Session, ctx: OrgContext, section_id: int | None) -> Section | None:
    if section_id is None:
        return None
    section = (
        db.query(Section)
        .filter(Section.id == section_id, Section.organization_id == ctx.org_id)
        .first()
    )
    if section is None:
        raise ValueError("Section not found in your school")
    return section


def create_worksheet(
    db: Session, ctx: OrgContext, req: WorksheetGenerateRequest
) -> Worksheet:
    school_class = _get_org_class(db, ctx, req.class_id)
    subject = _get_org_subject(db, ctx, req.subject_id)
    _get_org_section(db, ctx, req.section_id)
    ensure_teacher_can_access(db, ctx, req.class_id, req.subject_id)

    qwen = get_qwen_client()
    prompt = build_worksheet_prompt(
        class_name=school_class.name,
        subject_name=subject.name,
        topic=req.topic,
        counts=req.question_counts or QuestionCounts(),
        difficulty=req.difficulty,
        language=req.language,
        instructions=req.instructions,
        school_name=ctx.organization.name,
    )
    raw = qwen.chat(
        [
            {
                "role": "system",
                "content": (
                    "You are an expert worksheet generator for Pakistani schools. "
                    "Generate clear, structured, printable school worksheets with an "
                    "answer key and marking scheme. Follow the output format exactly."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=3500,
    )
    sections = split_generated_sections(raw)

    worksheet = Worksheet(
        organization_id=ctx.org_id,
        created_by_id=ctx.user.id,
        class_id=req.class_id,
        section_id=req.section_id,
        subject_id=req.subject_id,
        title=req.title or f"{subject.name} Worksheet - {req.topic}",
        topic=req.topic,
        instructions=req.instructions,
        difficulty=req.difficulty,
        language=req.language,
        question_types=(req.question_counts or QuestionCounts()).model_dump(),
        content=sections["content"],
        answer_key=sections["answer_key"],
        marking_scheme=sections["marking_scheme"],
    )
    db.add(worksheet)
    db.commit()
    db.refresh(worksheet)
    return worksheet


def create_test(db: Session, ctx: OrgContext, req: TestGenerateRequest) -> Test:
    school_class = _get_org_class(db, ctx, req.class_id)
    subject = _get_org_subject(db, ctx, req.subject_id)
    _get_org_section(db, ctx, req.section_id)
    ensure_teacher_can_access(db, ctx, req.class_id, req.subject_id)

    qwen = get_qwen_client()
    prompt = build_test_prompt(
        test_type=req.test_type,
        class_name=school_class.name,
        subject_name=subject.name,
        topic=req.topic,
        total_marks=req.total_marks,
        duration_minutes=req.duration_minutes,
        counts=req.question_counts or QuestionCounts(),
        difficulty=req.difficulty,
        language=req.language,
        instructions=req.instructions,
        school_name=ctx.organization.name,
    )
    raw = qwen.chat(
        [
            {
                "role": "system",
                "content": (
                    "You are an expert paper setter for Pakistani schools (weekly tests, "
                    "monthly tests, mid term and final term papers). Generate a balanced, "
                    "printable paper with an answer key and marking scheme. Follow the "
                    "output format exactly."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=3500,
    )
    sections = split_generated_sections(raw)

    test = Test(
        organization_id=ctx.org_id,
        created_by_id=ctx.user.id,
        class_id=req.class_id,
        section_id=req.section_id,
        subject_id=req.subject_id,
        test_type=req.test_type,
        title=req.title or f"{subject.name} - {_test_label(req.test_type)} - {school_class.name}",
        topic=req.topic,
        total_marks=req.total_marks,
        duration_minutes=req.duration_minutes,
        language=req.language,
        content=sections["content"],
        answer_key=sections["answer_key"],
        marking_scheme=sections["marking_scheme"],
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


def _test_label(test_type: str) -> str:
    return {
        "weekly": "Weekly Test",
        "monthly": "Monthly Test",
        "mid_term": "Mid Term Paper",
        "final_term": "Final Term Paper",
    }.get(test_type, "Test")
