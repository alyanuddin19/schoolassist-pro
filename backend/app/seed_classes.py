"""One-off helper: add Class 1-8 to every existing organization.

Run from the backend folder:
    python -m app.seed_classes

Safe to run multiple times (idempotent) — existing classes are skipped.
"""

from .database import SessionLocal
from .services.seed import backfill_default_classes


def main() -> None:
    db = SessionLocal()
    try:
        added = backfill_default_classes(db)
        print(f"Done. Added {added} class(es) across all organizations.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
