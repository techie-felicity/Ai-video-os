"""
One-off migration: adds project-level narration fields for an uploaded
voiceover file (replacing the earlier per-scene ElevenLabs-generated
narration approach). Safe to run multiple times.

Run from Railway's Console tab:
    python migrate_add_project_narration.py
"""
from sqlalchemy import text
from app.database import engine

STATEMENTS = [
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS narration_audio_uri VARCHAR",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS narration_duration_ms INTEGER",
]

if __name__ == "__main__":
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            print(f"Running: {stmt}")
            conn.execute(text(stmt))
    print("Done.")
