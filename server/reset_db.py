"""
reset_db.py — Drop all tables + enums, then recreate schema v2.0 from ORM models.

Run from the server/ directory:
    python reset_db.py           # reset schema only
    python reset_db.py --seed    # reset schema AND seed all clinical data

Uses DATABASE_URL_SYNC (psycopg2) from .env — same driver as Celery workers.
WARNING: This destroys ALL data. There is no undo.
"""

import sys
import sqlalchemy as sa
from sqlalchemy import text
from app.config import settings
from app.database import Base

# Import all models so Base.metadata knows about every table
import app.models  # noqa: F401 — side-effect import registers all ORM classes


ENUM_DEFINITIONS = [
    "CREATE TYPE patient_status AS ENUM ('pending', 'approved')",
    "CREATE TYPE task_type AS ENUM ('articulation', 'fluency', 'language', 'voice', 'motor_speech', 'social_communication', 'phonological', 'pragmatics', 'reading', 'writing', 'other')",
    "CREATE TYPE task_mode_type AS ENUM ('repeat', 'read_aloud', 'describe', 'answer', 'spontaneous', 'imitate', 'fill_blank', 'other')",
    "CREATE TYPE level_name AS ENUM ('beginner', 'elementary', 'intermediate', 'advanced', 'expert')",
    "CREATE TYPE prompt_type_enum AS ENUM ('exercise', 'warmup', 'assessment', 'review')",
    "CREATE TYPE baseline_domain AS ENUM ('articulation', 'fluency', 'language', 'voice', 'phonological', 'pragmatics', 'literacy', 'other')",
    "CREATE TYPE administration_method AS ENUM ('clinician_administered', 'self_administered', 'caregiver_assisted', 'automated')",
    "CREATE TYPE defect_category AS ENUM ('articulation', 'fluency', 'language', 'voice', 'motor_speech', 'social_communication', 'phonological', 'pragmatics', 'literacy', 'other')",
]


def reset():
    sync_url = settings.database_url_sync
    engine = sa.create_engine(sync_url, echo=True)

    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # close any open transaction

        print("\n==> Dropping public schema (CASCADE) ...")
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
        conn.execute(text("COMMIT"))

        print("\n==> Creating enum types ...")
        for ddl in ENUM_DEFINITIONS:
            conn.execute(text(ddl))
        conn.execute(text("COMMIT"))

    engine.dispose()

    print("\n==> Creating all tables from ORM models ...")
    engine = sa.create_engine(sync_url, echo=True)
    Base.metadata.create_all(engine)
    engine.dispose()

    print("\nDone! Database reset complete -- 27 tables created (v2.0 schema, no data).")


if __name__ == "__main__":
    seed_after = "--seed" in sys.argv

    confirm = input(
        "\nWARNING: This will DROP ALL TABLES AND DATA on the configured database.\n"
        "Type 'yes' to continue: "
    ).strip().lower()

    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)

    reset()

    if seed_after:
        print("\n==> Seeding clinical data ...")
        from seed_data import seed_all
        seed_all()
