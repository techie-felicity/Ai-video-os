"""
VisualAgent: for each shot, turns asset_type + surrounding scene context into
a concrete asset_spec (a query/prompt precise enough for VisualAgent's
downstream fetch/generate call in providers.py to act on). Kept separate from
actually calling the image/stock providers so this stays fast + cheap to run
and easy to preview/edit before committing to generation cost.
"""
from typing import Dict, Any


def run(shot: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
    asset_type = shot.get("asset_type", "stock")
    topics = ", ".join(scene.get("topics", []))
    entities = ", ".join(scene.get("entities", []))

    spec_by_type = {
        "stock": {"query": f"{topics} {entities}".strip(), "orientation": "landscape"},
        "ai_image": {"prompt": f"cinematic editorial photograph, {topics}, {entities}, documentary style",
                      "style": "cinematic"},
        "chart": {"chart_type": "auto", "data_topic": topics},
        "map": {"focus": entities or topics},
        "timeline": {"topic": topics},
        "website_recording": {"target": entities or topics},
        "ui_mockup": {"topic": topics},
        "motion_graphic": {"concept": topics},
    }
    shot["asset_spec"] = spec_by_type.get(asset_type, {"query": topics})
    return shot
