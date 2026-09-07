"""Seed helpers: subscription plans, default classes and default subjects."""

import re
import secrets

from sqlalchemy.orm import Session

from ..models import ClassSubject, Organization, SchoolClass, Subject, SubscriptionPlan

DEFAULT_PLANS = [
    # code, name, teacher seats, student seats, monthly price
    ("seats_25", "School Plan - 25 Teacher Seats", 25, 500, 2500.0),
    ("seats_30", "School Plan - 30 Teacher Seats", 30, 750, 3000.0),
    ("seats_50", "School Plan - 50 Teacher Seats", 50, 1500, 4800.0),
    ("seats_100", "School Plan - 100 Teacher Seats", 100, 3000, 8500.0),
]

# Subjects commonly taught in Pakistani schools
DEFAULT_SUBJECTS = [
    "English",
    "Urdu",
    "Mathematics",
    "Islamiat",
    "Science",
    "Physics",
    "Chemistry",
    "Biology",
    "Computer Science",
    "Social Studies",
]

# Primary/middle classes every Pakistani school starts with
DEFAULT_CLASSES = [
    ("Class 1", 1),
    ("Class 2", 2),
    ("Class 3", 3),
    ("Class 4", 4),
    ("Class 5", 5),
    ("Class 6", 6),
    ("Class 7", 7),
    ("Class 8", 8),
]

# Subjects taught per stage (names must exist in DEFAULT_SUBJECTS)
PRIMARY_SUBJECTS = ["English", "Urdu", "Mathematics", "Islamiat", "Science", "Social Studies"]
MIDDLE_SUBJECTS = PRIMARY_SUBJECTS + ["Computer Science"]
SECONDARY_SUBJECTS = [
    "English",
    "Urdu",
    "Mathematics",
    "Islamiat",
    "Physics",
    "Chemistry",
    "Biology",
    "Computer Science",
]


def default_subject_names_for_grade(grade_level: int | None) -> list[str]:
    """Sensible subject list for a grade (primary / middle / secondary)."""
    if grade_level is None:
        return list(DEFAULT_SUBJECTS)
    if grade_level <= 5:
        return list(PRIMARY_SUBJECTS)
    if grade_level <= 8:
        return list(MIDDLE_SUBJECTS)
    return list(SECONDARY_SUBJECTS)


def seed_subscription_plans(db: Session) -> None:
    for code, name, seats, student_seats, price in DEFAULT_PLANS:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()
        if existing is None:
            db.add(
                SubscriptionPlan(
                    code=code,
                    name=name,
                    teacher_seats=seats,
                    student_seats=student_seats,
                    price_pkr=price,
                    billing_period="monthly",
                    features=[
                        "All worksheet & test generators",
                        "Answer keys and marking schemes",
                        "Marksheet import and reports",
                        "Bilingual AI assistant (English / Urdu / Roman Urdu)",
                    ],
                )
            )
        elif existing.student_seats is None:
            # Plans created before student seats existed get the plan default.
            existing.student_seats = student_seats
    db.commit()


def seed_default_subjects(db: Session, organization_id: int) -> None:
    for name in DEFAULT_SUBJECTS:
        existing = (
            db.query(Subject)
            .filter(Subject.organization_id == organization_id, Subject.name == name)
            .first()
        )
        if existing is None:
            db.add(Subject(organization_id=organization_id, name=name))
    db.commit()


def seed_default_classes(db: Session, organization_id: int) -> None:
    """Add Class 1-8 to an organization (skips any that already exist)."""
    for name, grade_level in DEFAULT_CLASSES:
        existing = (
            db.query(SchoolClass)
            .filter(SchoolClass.organization_id == organization_id, SchoolClass.name == name)
            .first()
        )
        if existing is None:
            db.add(
                SchoolClass(organization_id=organization_id, name=name, grade_level=grade_level)
            )
    db.commit()


def backfill_default_classes(db: Session) -> int:
    """Add Class 1-8 to every existing organization missing them.

    Used by `python -m app.seed_classes` to upgrade orgs created before
    default class seeding existed. Returns the number of classes added.
    """
    added = 0
    orgs = db.query(Organization).all()
    for org in orgs:
        existing_names = {
            name
            for (name,) in db.query(SchoolClass.name).filter(
                SchoolClass.organization_id == org.id
            )
        }
        for name, grade_level in DEFAULT_CLASSES:
            if name not in existing_names:
                db.add(
                    SchoolClass(organization_id=org.id, name=name, grade_level=grade_level)
                )
                added += 1
    if added:
        db.commit()
    return added


def assign_default_subjects(db: Session, organization_id: int, school_class: SchoolClass) -> None:
    """Link a class to the default subjects for its grade level.

    Idempotent: classes that already have subject links are left untouched,
    so manual customization (Setup > Subjects per class) is never overwritten.
    """
    has_links = (
        db.query(ClassSubject.id)
        .filter(
            ClassSubject.organization_id == organization_id,
            ClassSubject.class_id == school_class.id,
        )
        .first()
        is not None
    )
    if has_links:
        return
    names = default_subject_names_for_grade(school_class.grade_level)
    subjects = (
        db.query(Subject)
        .filter(Subject.organization_id == organization_id, Subject.name.in_(names))
        .all()
    )
    if not subjects:
        # Org renamed/removed the default subjects: fall back to everything it has
        subjects = db.query(Subject).filter(Subject.organization_id == organization_id).all()
    for subject in subjects:
        db.add(
            ClassSubject(
                organization_id=organization_id,
                class_id=school_class.id,
                subject_id=subject.id,
            )
        )
    db.commit()


def seed_default_class_subjects(db: Session, organization_id: int) -> None:
    """Give every class of an organization its default subject list."""
    classes = (
        db.query(SchoolClass).filter(SchoolClass.organization_id == organization_id).all()
    )
    for school_class in classes:
        assign_default_subjects(db, organization_id, school_class)


def unique_slug(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "school").lower()).strip("-")[:60] or "school"
    slug = base
    while db.query(Organization).filter(Organization.slug == slug).first() is not None:
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug
