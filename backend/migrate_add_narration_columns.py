"""
One-off migration: adds the columns needed for real TTS narration + per-shot
captions. Safe to run multiple times (uses IF NOT EXISTS) and safe regardless
of whether your DB schema was created via Alembic or via
Base.metadata.create_all() — this doesn't touch either of those systems, it
just runs plain ALTER TABLE statements directly.

Run this ONCE from Railway's Console/Shell tab for your backend service:

    python migrate_add_narration_columns.py

(Or `python -m app.migrate_add_narration_columns` depending on where you
place this file — adjust the import below to match your project's existing
database setup.)
"""
from sqlalchemy import text
from app.database import engine  # adjust import if your engine lives elsewhere

STATEMENTS = [
    "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS narration_audio_uri VARCHAR",
    "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS narration_duration_ms INTEGER",
    "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS word_timestamps JSON DEFAULT '[]'::json",
    "ALTER TABLE shots ADD COLUMN IF NOT EXISTS caption_text TEXT",
]

if __name__ == "__main__":
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            print(f"Running: {stmt}")
            conn.execute(text(stmt))
    print("Done. All columns present (created or already existed).")
