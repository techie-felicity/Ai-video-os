"""
AudioAgent: maps a scene's music_intensity + per-shot reveal flags into
concrete audio cues (cue changes, ducking, SFX triggers). Actual music/SFX
selection calls out to providers.select_music_cue — kept separate so this
agent can run cheaply against every shot without hitting external APIs.
"""
from typing import Dict, Any

INTENSITY_TO_PARAMS = {
    "none": {"music_gain_db": -100, "duck_voice": False},
    "low": {"music_gain_db": -18, "duck_voice": True},
    "building": {"music_gain_db": -12, "duck_voice": True, "riser": True},
    "high": {"music_gain_db": -8, "duck_voice": True},
    "drop": {"music_gain_db": -100, "duck_voice": False, "impact_sfx": True},
}


def run(shot: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
    intensity = scene.get("editorial_directives", {}).get("music_intensity", "low")
    cues = dict(INTENSITY_TO_PARAMS.get(intensity, INTENSITY_TO_PARAMS["low"]))
    if shot.get("motion_params", {}).get("is_reveal"):
        cues["impact_sfx"] = True
        cues["music_gain_db"] = max(cues["music_gain_db"], -10)
    shot["audio_cues"] = cues
    return shot
