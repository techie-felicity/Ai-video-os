"""
Orchestrator: runs the full agent pipeline for a project and persists the
Scene Graph incrementally (so the frontend can poll/stream progress and a
user could in principle intervene between stages later).

Pipeline order matches README §2:
ScriptAgent -> EditorAgent -> StoryboardAgent -> Visual/Motion/Audio/Subtitle
"""
import time
import logging
from sqlalchemy.orm import Session

from app import models
from app.agents import (
    script_agent, editor_agent, storyboard_agent,
    visual_agent, motion_agent, audio_agent, subtitle_agent, providers,
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

        # NOTE: narration is no longer generated here (ElevenLabs removed).
        # If the user uploaded a voiceover via POST /projects/{id}/narration
        # before calling /generate, _rescale_to_narration() below applies it
        # project-wide once all scenes/shots exist. Until then, shots keep
        # their LLM word-count-estimated duration_ms and caption_text falls
        # back to the full scene script text.

        t0 = time.time()
        raw_shots = storyboard_agent.run(raw_scene)
        _log_run(db, project.id, "storyboard_agent", raw_scene, raw_shots, t0)

        for s in raw_shots:
            s.setdefault("caption_text", scene.script_text)

        for shot_data in raw_shots:
            shot_data = visual_agent.run(shot_data, raw_scene)
            shot_data = motion_agent.run(shot_data, raw_scene.get("tension_score", 0.3))
            shot_data = audio_agent.run(shot_data, raw_scene)
            shot_data = subtitle_agent.run(shot_data, raw_scene, brand_kit)

            # Resolve a real asset where we have a provider wired up.
            # Anything else (chart/map/timeline/ai_image/etc.) still falls
            # back to the placeholder renderer for now — logged, not fatal.
            asset_id = None
            if shot_data["asset_type"] == "stock":
                try:
                    result = providers.search_stock_footage(shot_data["asset_spec"].get("query", ""))
                    asset = models.Asset(
                        type="image",
                        provider=result["provider"],
                        uri=result["uri"],
                        asset_metadata=result.get("metadata", {}),
                    )
                    db.add(asset)
                    db.flush()
                    asset_id = asset.id
                except Exception as e:
                    logging.getLogger(__name__).warning(f"search_stock_footage failed: {e}")

            db.add(models.Shot(
                scene_id=scene.id,
                order=shot_data["order"],
                duration_ms=shot_data["duration_ms"],
                camera_move=shot_data["camera_move"],
                transition_in=shot_data["transition_in"],
                asset_type=shot_data["asset_type"],
                asset_spec=shot_data["asset_spec"],
                asset_id=asset_id,
                motion_params=shot_data["motion_params"],
                audio_cues=shot_data["audio_cues"],
                subtitle_params=shot_data["subtitle_params"],
                caption_text=shot_data["caption_text"],
            ))

        # Commit after each fully-generated scene. If a later scene fails
        # (e.g. hits an LLM rate limit), everything up to here is already
        # safely persisted and won't be rolled back with it.
        db.commit()

    # Applied once, only if a voiceover was uploaded before /generate was
    # called. Guarded by the ready_to_render status transition below — once
    # a project reaches ready_to_render, /generate refuses to run again, so
    # this can't accidentally double-apply the scale factor on a rerun.
    if project.narration_audio_uri and project.narration_duration_ms:
        _rescale_to_narration(db, project)

    project.status = models.ProjectStatus.ready_to_render
    db.commit()
    db.refresh(project)
    return project


def _rescale_to_narration(db: Session, project: models.Project) -> None:
    """
    Stretches/compresses every shot's duration so the total matches the
    uploaded voiceover's real length exactly (preserving each shot's
    relative weight from the LLM's original estimate), then distributes the
    full script's words across shots proportionally to their new duration
    share. This is an approximation (no true word-level alignment, since
    there's no forced-alignment step for uploaded audio) but is a large
    improvement over one full scene of caption text sitting static across
    every shot in that scene.
    """
    all_shots = [sh for s in project.scenes for sh in s.shots]
    if not all_shots:
        return

    estimated_total_ms = sum(sh.duration_ms for sh in all_shots) or 1
    scale = project.narration_duration_ms / estimated_total_ms
    for sh in all_shots:
        sh.duration_ms = max(500, round(sh.duration_ms * scale))

    full_words = " ".join(s.script_text for s in project.scenes).split()
    total_words = len(full_words) or 1
    total_new_ms = sum(sh.duration_ms for sh in all_shots) or 1

    word_cursor = 0
    for sh in all_shots:
        share = sh.duration_ms / total_new_ms
        word_count = max(1, round(share * total_words))
        word_slice = full_words[word_cursor: word_cursor + word_count]
        if word_slice:
            sh.caption_text = " ".join(word_slice)
        word_cursor += word_count

    db.commit()
