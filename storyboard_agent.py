"""
StoryboardAgent: turns each scene's editorial_directives into a concrete,
ordered shot list — the last purely "editorial" step before asset planning
takes over. Deterministic where possible (duration math from cut_cadence),
model-assisted where judgment is needed (transition/camera-move choice).
"""
import math
from typing import List, Dict, Any
from app.agents.providers import call_reasoning_model

SYSTEM_PROMPT = """You are a storyboard artist working from an editor's
directives. For ONE scene, propose a shot list: for each shot choose a
camera_move (static, push_in, push_out, pan_left, pan_right, tilt_up,
tilt_down, handheld_drift) and transition_in (cut, crossfade, whip_pan,
glitch, match_cut, hard_flash). Match energy to the scene's tension_score and
music_intensity — high tension/building music favors whip_pan/glitch and
push_in; calm/explanatory beats favor cut/crossfade and static/slow push.

Return ONLY JSON: {"shots": [{"camera_move": "...", "transition_in": "..."}]}
— exactly `shot_count` entries. No prose, no markdown fences."""


def _estimate_scene_duration_ms(script_text: str) -> int:
    # ~150 wpm narration pace as a rough estimate; refined later once TTS audio exists.
    words = len(script_text.split())
    return max(2000, int(words / 150 * 60 * 1000))


def run(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    directives = scene.get("editorial_directives", {})
    cadence_s = directives.get("cut_cadence_seconds", 4)
    duration_ms = _estimate_scene_duration_ms(scene["script_text"])
    shot_count = max(1, math.ceil((duration_ms / 1000) / cadence_s))
    per_shot_ms = duration_ms // shot_count

    user_prompt = (
        f"Scene text: {scene['script_text']}\n"
        f"tension_score: {scene.get('tension_score', 0.3)}\n"
        f"music_intensity: {directives.get('music_intensity', 'low')}\n"
        f"shot_count: {shot_count}"
    )
    result = call_reasoning_model(SYSTEM_PROMPT, user_prompt)
    proposals = result.get("shots", [])

    shots = []
    for i in range(shot_count):
        proposal = proposals[i] if i < len(proposals) else {}
        shots.append({
            "order": i,
            "duration_ms": per_shot_ms,
            "camera_move": proposal.get("camera_move", "static"),
            "transition_in": "cut" if i == 0 else proposal.get("transition_in", "cut"),
            "asset_type": directives.get("suggested_visual_mode", "stock"),
            "asset_spec": {},
            "motion_params": {},
            "audio_cues": {},
            "subtitle_params": {},
        })

    if shots and directives.get("reveal_moment"):
        shots[-1]["motion_params"]["is_reveal"] = True
        shots[-1]["duration_ms"] += directives.get("pause_before_ms", 0)

    return shots
