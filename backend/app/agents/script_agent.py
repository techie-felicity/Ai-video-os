"""
ScriptAgent: reads the raw script, segments it into narrative beats ("scenes"),
and tags each with topics, entities, and an emotional read. This is the
foundation the EditorAgent reasons over — get segmentation granularity right
(roughly one scene per 1-3 sentences / 8-20 seconds of narration) and
everything downstream gets easier.
"""
from typing import List, Dict, Any
from app.agents.providers import call_reasoning_model

SYSTEM_PROMPT = """You are a documentary script analyst. Segment scripts into
narrative beats the way a professional editor would mark up a script before
cutting — not by sentence, but by *idea unit*: a beat ends when the topic,
tone, or narrative function changes.

For each beat, extract:
- topics: short noun phrases (max 4) capturing what's being discussed
- entities: named people/places/organizations/products mentioned
- emotion: single word describing the emotional register (e.g. curiosity,
  tension, relief, awe, humor, urgency, melancholy)

Return ONLY a JSON object: {"scenes": [{"script_text": "...", "topics": [...],
"entities": [...], "emotion": "..."}]}. No prose, no markdown fences."""


def run(script: str) -> List[Dict[str, Any]]:
    user_prompt = f"Segment this documentary script:\n\n{script}"
    result = call_reasoning_model(SYSTEM_PROMPT, user_prompt)
    scenes = result.get("scenes", [])
    for i, scene in enumerate(scenes):
        scene.setdefault("order", i)
        scene.setdefault("topics", [])
        scene.setdefault("entities", [])
        scene.setdefault("emotion", "neutral")
    return scenes
