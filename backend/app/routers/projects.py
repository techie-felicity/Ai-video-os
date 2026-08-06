from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.agents.orchestrator import run_pipeline

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)):
    project = models.Project(
        title=payload.title,
        script=payload.script,
        platform=payload.platform,
        target_length_seconds=payload.target_length_seconds,
        brand_kit_id=payload.brand_kit_id,
        voice_profile_id=payload.voice_profile_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).order_by(models.Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("/{project_id}/generate", response_model=schemas.ProjectOut)
def generate_scene_graph(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Kicks off the full agent pipeline (Script -> Editor -> Storyboard ->
    Visual/Motion/Audio/Subtitle). Runs in the background; poll
    GET /projects/{id}/scene-graph for progress via project.status.
    """
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    # Only block if this project already finished the scene-graph stage (or
    # moved further along, e.g. into rendering). A project stuck in
    # scripting/storyboarding/failed can still resume — run_pipeline skips
    # any scenes that already completed in a prior attempt.
    if project.status in (
        models.ProjectStatus.ready_to_render,
        models.ProjectStatus.rendering,
        models.ProjectStatus.rendered,
    ):
        raise HTTPException(400, "Scene graph already generated for this project")

    background_tasks.add_task(_run_pipeline_isolated, project_id)
    project.status = models.ProjectStatus.scripting
    db.commit()
    db.refresh(project)
    return project


def _run_pipeline_isolated(project_id: str):
    # Background tasks need their own DB session, separate from the request's.
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        project = db.get(models.Project, project_id)
        run_pipeline(db, project)
    except Exception as e:
        project = db.get(models.Project, project_id)
        if project:
            project.status = models.ProjectStatus.failed
            db.commit()
        raise e
    finally:
        db.close()


@router.get("/{project_id}/scene-graph", response_model=schemas.SceneGraphOut)
def get_scene_graph(project_id: str, db: Session = Depends(get_db)):
    project = db.query(models.Project).options(
        joinedload(models.Project.scenes).joinedload(models.Scene.shots)
    ).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project": project, "scenes": project.scenes}
