"""
Thin provider interfaces so every agent talks to an abstraction, never to a
vendor SDK directly. Swap implementations here without touching agent logic.

Fill in real API calls where marked TODO. Kept synchronous + simple on
purpose — wrap with asyncio.to_thread from callers if you need concurrency.
"""
import os
import json
from typing import Any, Dict

import anthropic

_client = None


def get_llm_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def call_reasoning_model(system_prompt: str, user_prompt: str, model: str = "claude-sonnet-5") -> Dict[str, Any]:
    """
    Used by ScriptAgent, EditorAgent, StoryboardAgent, VisualAgent for structured
    JSON reasoning. Expects the model to return ONLY JSON (enforced via prompt).
    """
    client = get_llm_client()
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("json", 1)[-1] if text.lower().startswith("json") else text
    return json.loads(text)


def generate_image(prompt: str, style: str = "cinematic") -> str:
    """TODO: wire to Flux/SDXL/Ideogram. Returns an asset URI."""
    raise NotImplementedError("Wire this to your image generation provider (Flux/SDXL/Ideogram).")


def search_stock_footage(query: str) -> Dict[str, Any]:
    """TODO: wire to Pexels/Storyblocks API. Returns asset metadata + URI."""
    raise NotImplementedError("Wire this to a licensed stock footage provider.")


def synthesize_speech(text: str, voice_id: str) -> str:
    """TODO: wire to ElevenLabs/Azure TTS. Returns audio asset URI."""
    raise NotImplementedError("Wire this to your TTS provider.")


def select_music_cue(mood: str, duration_ms: int) -> Dict[str, Any]:
    """TODO: wire to a licensed, mood-tagged music library (Soundstripe/Epidemic/Suno)."""
    raise NotImplementedError("Wire this to your music library provider.")
