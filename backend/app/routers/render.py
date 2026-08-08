import json
import re
import subprocess
import tempfile
import os

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas, render_queue

router = APIRouter(prefix="/render", tags=["render"])

RENDER_ENGINE_DIR = os.getenv("RENDER_ENGINE_DIR", "/app/render-engine")
OUTPUT_DIR = os.getenv("RENDER_OUTPUT_DIR", "/tmp/renders")


@router.post("/{project_id}", response_model=schemas.RenderJobOut)
def start_render(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.query(models.Project).options(
        joinedload(models.Project.scenes).joinedload(models.Scene.shots)
    ).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if project.status != models.ProjectStatus.ready_to_render:
        raise HTTPException(400, f"Project not ready to render (status={project.status})")

    job = render_queue.enqueue(db, project_id)
    background_tasks.add_task(_render_isolated, job.id)
    return job


@router.get("/{job_id}", response_model=schemas.RenderJobOut)
def get_render_status(job_id: str, db: Session = Depends(get_db)):
    job = db.get(models.RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Render job not found")
    return job


@router.get("/{job_id}/download")
def download_render(job_id: str, db: Session = Depends(get_db)):
    job = db.get(models.RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Render job not found")
    if job.status != "done" or not job.output_uri:
        raise HTTPException(400, f"Render not finished yet (status={job.status})")
    if not os.path.exists(job.output_uri):
        # /tmp is ephemeral: if the container restarted/redeployed since this
        # job finished, the file is gone even though the DB still says done.
        raise HTTPException(
            410,
            "Rendered file no longer exists on disk (likely lost on a "
            "restart/redeploy since /tmp doesn't persist). Re-render to get "
            "a fresh copy.",
        )
    return FileResponse(
        job.output_uri,
        media_type="video/mp4",
        filename=f"{job.project_id}.mp4",
    )


def _scene_graph_to_remotion_props(project: models.Project) -> dict:
    return {
        "title": project.title,
        "platform": project.platform.value if hasattr(project.platform, "value") else project.platform,
        "narrationAudioUri": project.narration_audio_uri,
        "brandKit": {
            "primaryColor": project.brand_kit.primary_color if project.brand_kit else "#111111",
            "accentColor": project.brand_kit.accent_color if project.brand_kit else "#FF4D00",
            "fontHeading": project.brand_kit.font_heading if project.brand_kit else "Inter",
        } if project.brand_kit else None,
        "scenes": [
            {
                "order": s.order,
                "scriptText": s.script_text,
                "shots": [
                    {
                        "order": sh.order,
                        "durationMs": sh.duration_ms,
                        "cameraMove": sh.camera_move,
                        "transitionIn": sh.transition_in,
                        "assetType": sh.asset_type,
                        "assetSpec": sh.asset_spec,
                        "assetUri": sh.asset.uri if sh.asset else None,
                        "motionParams": sh.motion_params,
                        "audioCues": sh.audio_cues,
                        "subtitleParams": sh.subtitle_params,
                        "captionText": sh.caption_text or s.script_text,
                    } for sh in s.shots
                ],
            } for s in project.scenes
        ],
    }


def _render_isolated(job_id: str):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        job = db.get(models.RenderJob, job_id)
        project = db.query(models.Project).options(
            joinedload(models.Project.scenes)
            .joinedload(models.Scene.shots)
            .joinedload(models.Shot.asset),
        ).filter(models.Project.id == job.project_id).first()

        db_project_status = models.ProjectStatus.rendering
        project.status = db_project_status
        db.commit()

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        props = _scene_graph_to_remotion_props(project)

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(props, f)
            props_path = f.name

        output_path = os.path.join(OUTPUT_DIR, f"{project.id}.mp4")

        # Delegates to render-engine/render.js, which runs Remotion + FFmpeg.
        # See render-engine/render.js for the full pipeline (frames -> mux -> master).
        result = subprocess.run(
            ["node", "render.js", "--props", props_path, "--output", output_path],
            cwd=RENDER_ENGINE_DIR,
            capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0:
            # Store the FULL, unfiltered stderr so the real error is visible
            # via GET /render/{job_id} — no truncation, no line filtering.
            # (Previous versions filtered ffmpeg progress lines and truncated
            # to 4000 chars, which risked eating the actual failure reason
            # along with the noise.)
            raise RuntimeError(f"Render failed (exit {result.returncode}): {result.stderr}")

        render_queue.mark_done(db, job, output_path)
        project.status = models.ProjectStatus.rendered
        db.commit()
    except Exception as e:
        job = db.get(models.RenderJob, job_id)
        if job:
            render_queue.mark_failed(db, job, str(e))
        project = db.get(models.Project, job.project_id) if job else None
        if project:
            project.status = models.ProjectStatus.failed
            db.commit()
    finally:
        db.close()
