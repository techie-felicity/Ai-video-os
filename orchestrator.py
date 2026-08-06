"""
Orchestrator: runs the full agent pipeline for a project and persists the
Scene Graph incrementally (so the frontend can poll/stream progress and a
user could in principle intervene between stages later).

Pipeline order matches README §2:
ScriptAgent -> EditorAgent -> StoryboardAgent -> Visual/Motion/Audio/Subtitle
"""
import time
from sqlalchemy.orm import Session

from app import models
from app.agents import (
    script_agent, editor_agent, storyboard_agent,
    visual_agent, motion_agent, audio_agent, subtitle_agent,
)


def _log_run(db: Session, project_id: str, agent_name: str, input_payload, output_payload, started_at: float):
    db.add(models.AgentRun(
        project_id=project_id,
        agent_name=agent_name,
        latency_ms=int((time.time() - started_at) * 1000),
        input_payload=input_payload if isinstance(input_payload, (dict, list)) else str(input_payload),
        output_payload=output_payload if isinstance(output_payload, (dict, list)) else str(output_payload),
    ))
    db.commit()


def run_pipeline(db: Session, project: models.Project) -> models.Project:
    project.status = models.ProjectStatus.scripting
    db.commit()

    t0 = time.time()
    raw_scenes = script_agent.run(project.script)
    _log_run(db, project.id, "script_agent", project.script, raw_scenes, t0)

    t0 = time.time()
    raw_scenes = editor_agent.run(raw_scenes)
    _log_run(db, project.id, "editor_agent", None, raw_scenes, t0)

    project.status = models.ProjectStatus.storyboarding
    db.commit()

    brand_kit = None
    if project.brand_kit:
        brand_kit = {
            "font_body": project.brand_kit.font_body,
            "accent_color": project.brand_kit.accent_color,
        }

    # Resume support: if a previous attempt crashed partway through (e.g. an
    # LLM rate limit on scene 3 of 5), don't re-burn tokens regenerating
    # scenes that already completed and were committed in an earlier attempt.
    existing_scenes_by_order = {s.order: s for s in project.scenes}

    for i, raw_scene in enumerate(raw_scenes):
        existing = existing_scenes_by_order.get(i)
        if existing and existing.shots:
            continue  # already fully generated in a prior attempt — skip

        scene = existing
        if scene is None:
            scene = models.Scene(
                project_id=project.id,
                order=i,
                script_text=raw_scene["script_text"],
                topics=raw_scene["topics"],
                entities=raw_scene["entities"],
                emotion=raw_scene["emotion"],
                tension_score=raw_scene["tension_score"],
                editorial_directives=raw_scene["editorial_directives"],
            )
            db.add(scene)
            db.flush()  # get scene.id

        t0 = time.time()
        raw_shots = storyboard_agent.run(raw_scene)
        _log_run(db, project.id, "storyboard_agent", raw_scene, raw_shots, t0)

        for shot_data in raw_shots:
            shot_data = visual_agent.run(shot_data, raw_scene)
            shot_data = motion_agent.run(shot_data, raw_scene.get("tension_score", 0.3))
            shot_data = audio_agent.run(shot_data, raw_scene)
            shot_data = subtitle_agent.run(shot_data, raw_scene, brand_kit)

            db.add(models.Shot(
                scene_id=scene.id,
                order=shot_data["order"],
                duration_ms=shot_data["duration_ms"],
                camera_move=shot_data["camera_move"],
                transition_in=shot_data["transition_in"],
                asset_type=shot_data["asset_type"],
                asset_spec=shot_data["asset_spec"],
                motion_params=shot_data["motion_params"],
                audio_cues=shot_data["audio_cues"],
                subtitle_params=shot_data["subtitle_params"],
            ))

        # Commit after each fully-generated scene. If a later scene fails
        # (e.g. hits an LLM rate limit), everything up to here is already
        # safely persisted and won't be rolled back with it.
        db.commit()

    project.status = models.ProjectStatus.ready_to_render
    db.commit()
    db.refresh(project)
    return project
