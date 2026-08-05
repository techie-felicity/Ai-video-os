"""
SubtitleAgent: styling/timing for captions on a shot. Kept simple and
deterministic — caption *content* comes from the script text + TTS word
timestamps (wired in once synthesize_speech is implemented); this agent only
decides presentation.
"""
from typing import Dict, Any


def run(shot: Dict[str, Any], scene: Dict[str, Any], brand_kit: Dict[str, Any] | None = None) -> Dict[str, Any]:
    brand_kit = brand_kit or {}
    emphasis = scene.get("tension_score", 0.3) > 0.6

    shot["subtitle_params"] = {
        "font": brand_kit.get("font_body", "Inter"),
        "position": "bottom_center",
        "highlight_color": brand_kit.get("accent_color", "#FF4D00") if emphasis else None,
        "animation": "word_pop" if emphasis else "fade_in",
        "max_words_per_line": 4,
    }
    return shot
