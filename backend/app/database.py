from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .core.config import settings


def _engine_options(url: str) -> dict:
    if url.startswith("sqlite"):
        # SQLite needs this when used with FastAPI's threadpool
        return {"connect_args": {"check_same_thread": False}}
    # PostgreSQL / Supabase: keep connections healthy behind poolers
    return {"pool_pre_ping": True, "pool_recycle": 1800}


engine = create_engine(settings.DATABASE_URL, **_engine_options(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_schema() -> list[str]:
    """Create missing tables and add columns introduced after the DB was made.

    ``create_all`` never alters an existing table, so a SQLite file created by
    an older version of the models would raise "no such column". Adding a
    nullable column is supported by both SQLite and PostgreSQL, which keeps the
    MVP free of Alembic migrations.
    """
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    known_tables = set(inspector.get_table_names())
    added: list[str] = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in known_tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}')
                )
                added.append(f"{table.name}.{column.name}")
    # Seating plans became term-wide (rooms mix several classes), so the class
    # reference had to become optional on databases created by older models.
    with engine.begin() as conn:
        try:
            conn.execute(
                text('ALTER TABLE "seating_plans" ALTER COLUMN "class_id" DROP NOT NULL')
            )
        except Exception:
            pass  # SQLite cannot relax NOT NULL; fresh databases are already nullable
    return added
