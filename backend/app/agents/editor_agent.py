"""
EditorAgent — the taste layer. This is the component worth protecting and
iterating on obsessively; everything else in this repo is plumbing.

Input: the full ordered scene list from ScriptAgent (it needs the whole
script in view to reason about arc, not just one beat at a time — tension
only means something relative to what came before and what's coming).

Output: per-scene editorial directives that StoryboardAgent turns into a
concrete shot list. Keep directives declarative (WHAT should happen) rather
than prescriptive (HOW to render it) so StoryboardAgent/VisualAgent retain
room to make good concrete choices.

Tune this prompt against your own annotated examples of well-paced
documentary editing — never against copyrighted footage or a specific
creator's branded assets. You're teaching the model editorial *principles*
(pacing, tension curves, reveal timing), not reproducing anyone's work.
"""
from typing import List, Dict, Any
from app.agents.providers import call_reasoning_model

SYSTEM_PROMPT = """You are a senior documentary editor (think: the pacing
sensibility of long-form YouTube explainer/documentary channels — fast cuts
during tension build, held shots during emotional beats, deliberate pauses
before reveals). You do not generate footage. You make editorial calls.

Given an ordered list of narrative beats (each with text/topics/entities/
emotion), assign each beat a tension_score (0.0-1.0, relative to the whole
arc — build toward peaks, allow release after them) and editorial_directives:

- cut_cadence_seconds: target seconds per cut in this beat (faster during
  tension build, e.g. 1.5-2.5s; slower during emotional/explanatory beats,
  e.g. 4-7s)
- pause_before_ms: silence/held-frame before this beat, if it's a reveal (0
  if not applicable)
- music_intensity: "none" | "low" | "building" | "high" | "drop"
  (drop = music cuts out for emphasis)
  - reveal_moment: true/false — does this beat deserve a visual "reveal" (chart
  appearing, map zooming in, etc.) rather than just cutting to it
- suggested_visual_mode: one of stock, ai_image, chart, map, timeline,
  website_recording, ui_mockup, motion_graphic — pick what best serves the
  IDEA, not decoration

Return ONLY JSON: {"scenes": [{"order": 0, "tension_score": 0.3,
"editorial_directives": {...}}]} — one entry per input scene, same order.
No prose, no markdown fences."""


def run(scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compact = [
        {"order": i, "text": s["script_text"], "topics": s["topics"],
         "emotion": s["emotion"]}
        for i, s in enumerate(scenes)
    ]
    user_prompt = f"Full beat sequence (make relative tension calls across the whole arc):\n\n{compact}"
    result = call_reasoning_model(SYSTEM_PROMPT, user_prompt)
    directives_by_order = {d["order"]: d for d in result.get("scenes", [])}

    for i, scene in enumerate(scenes):
        d = directives_by_order.get(i, {})
        scene["tension_score"] = d.get("tension_score", 0.3)
        scene["editorial_directives"] = d.get("editorial_directives", {
            "cut_cadence_seconds": 4,
            "pause_before_ms": 0,
            "music_intensity": "low",
            "reveal_moment": False,
            "suggested_visual_mode": "stock",
        })
    return scenes
