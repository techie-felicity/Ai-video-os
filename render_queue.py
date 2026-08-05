"""
Minimal Postgres-backed render queue. Swap for Redis/RQ, SQS, or Cloud Tasks
later — calling code only depends on enqueue/claim_next/mark_done/mark_failed,
so the swap doesn't touch routers or the orchestrator.
"""
from sqlalchemy.orm import Session
from sqlalchemy import select

from app import models


def enqueue(db: Session, project_id: str) -> models.RenderJob:
    job = models.RenderJob(project_id=project_id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next(db: Session) -> models.RenderJob | None:
    job = db.execute(
        select(models.RenderJob).where(models.RenderJob.status == "queued").limit(1)
    ).scalar_one_or_none()
    if job:
        job.status = "running"
        db.commit()
        db.refresh(job)
    return job


def update_progress(db: Session, job: models.RenderJob, progress: float):
    job.progress = progress
    db.commit()


def mark_done(db: Session, job: models.RenderJob, output_uri: str):
    job.status = "done"
    job.progress = 1.0
    job.output_uri = output_uri
    db.commit()


def mark_failed(db: Session, job: models.RenderJob, error: str):
    job.status = "failed"
    job.error = error
    db.commit()
