"""
MotionAgent: deterministic camera-math layer. Camera moves don't need an LLM
— they need consistent, physically-plausible parameters derived from the
camera_move label + shot duration + tension. Style *selection* upstream
(StoryboardAgent) is where judgment lives; this agent just executes it well.
"""
from typing import Dict, Any

MOVE_PRESETS = {
    "static": {"zoom_start": 1.0, "zoom_end": 1.0, "pan_x": 0, "pan_y": 0},
    "push_in": {"zoom_start": 1.0, "zoom_end": 1.12, "pan_x": 0, "pan_y": 0},
    "push_out": {"zoom_start": 1.12, "zoom_end": 1.0, "pan_x": 0, "pan_y": 0},
    "pan_left": {"zoom_start": 1.05, "zoom_end": 1.05, "pan_x": -40, "pan_y": 0},
    "pan_right": {"zoom_start": 1.05, "zoom_end": 1.05, "pan_x": 40, "pan_y": 0},
    "tilt_up": {"zoom_start": 1.05, "zoom_end": 1.05, "pan_x": 0, "pan_y": -30},
    "tilt_down": {"zoom_start": 1.05, "zoom_end": 1.05, "pan_x": 0, "pan_y": 30},
    "handheld_drift": {"zoom_start": 1.03, "zoom_end": 1.06, "pan_x": 8, "pan_y": 6, "jitter": True},
}


def run(shot: Dict[str, Any], tension_score: float) -> Dict[str, Any]:
    preset = dict(MOVE_PRESETS.get(shot.get("camera_move", "static"), MOVE_PRESETS["static"]))
    # Higher tension = slightly more aggressive push, subtle blur on transitions.
    if tension_score > 0.6:
        preset["zoom_end"] = round(preset["zoom_end"] * 1.03, 3)
        preset["transition_blur"] = True
    preset["is_reveal"] = shot.get("motion_params", {}).get("is_reveal", False)
    shot["motion_params"] = preset
    return shot
