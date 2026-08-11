"""
Thin provider interfaces so every agent talks to an abstraction, never to a
vendor SDK directly. Swap implementations here without touching agent logic.

Fill in real API calls where marked TODO. Kept synchronous + simple on
purpose — wrap with asyncio.to_thread from callers if you need concurrency.
"""
import os
import re
import json
import time
import logging
import requests
from typing import Any, Dict

from openai import OpenAI, RateLimitError, APIStatusError

logger = logging.getLogger(__name__)

ASSETS_DIR = os.environ.get("ASSETS_DIR", "/app/assets")

_client = None


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _client


def _extract_retry_seconds(err: Exception, default: float = 5.0) -> float:
    """
    Rate-limit error bodies sometimes include an explicit retry hint —
    Groq writes 'try again in 18.125s', Gemini's underlying error includes
    a RetryInfo block like '"retryDelay": "18s"'. Check both formats,
    otherwise fall back to the caller-supplied default (exponential backoff).
    """
    message = str(err)
    match = re.search(r"try again in ([\d.]+)s", message)
    if not match:
        match = re.search(r'retryDelay["\']?\s*:\s*["\']?([\d.]+)s', message)
    if match:
        try:
            return float(match.group(1)) + 0.5  # small buffer
        except ValueError:
            pass
    return default


def call_reasoning_model(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemini-3.6-flash",
    max_retries: int = 4,
) -> Dict[str, Any]:
    """
    Used by ScriptAgent, EditorAgent, StoryboardAgent, VisualAgent for structured
    JSON reasoning. Expects the model to return ONLY JSON (enforced via prompt).

    "gemini-3.6-flash" is the default: Google's current-generation stable Flash
    model (GA as of mid-2026), replacing "gemini-2.5-flash" which is deprecated
    and returns 404 for new API keys/projects. If you hit request-count limits
    during heavy testing, "gemini-3.5-flash-lite" is a lighter/cheaper fallback
    with the same call signature.

    Retries on rate limits (429) using whatever wait time the error message
    suggests, with exponential backoff as a fallback if that's absent.
    """
    client = get_llm_client()

    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=4000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            break
        except RateLimitError as e:
            attempt += 1
            if attempt > max_retries:
                logger.error(f"call_reasoning_model: exceeded {max_retries} retries on rate limit: {e}")
                raise
            wait_s = _extract_retry_seconds(e, default=2 ** attempt)
            logger.warning(
                f"call_reasoning_model: rate limited (attempt {attempt}/{max_retries}), "
                f"waiting {wait_s:.1f}s before retry"
            )
            time.sleep(wait_s)
        except APIStatusError as e:
            # Retry on transient server-side errors (5xx); anything else re-raises.
            if e.status_code >= 500 and attempt < max_retries:
                attempt += 1
                wait_s = 2 ** attempt
                logger.warning(
                    f"call_reasoning_model: server error {e.status_code} "
                    f"(attempt {attempt}/{max_retries}), waiting {wait_s:.1f}s"
                )
                time.sleep(wait_s)
                continue
            raise

    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("json", 1)[-1] if text.lower().startswith("json") else text
    return json.loads(text)


def generate_image(prompt: str, style: str = "cinematic") -> str:
    """TODO: wire to Flux/SDXL/Ideogram. Returns an asset URI."""
    raise NotImplementedError("Wire this to your image generation provider (Flux/SDXL/Ideogram).")


def search_stock_footage(query: str, orientation: str = "landscape") -> Dict[str, Any]:
    """
    Searches Pexels for a photo matching `query`. Returns asset metadata +
    a direct image URI that Remotion can load into a shot.

    Uses the Photos API (not Videos) — shots are currently rendered as
    still image2 frames, so a photo result matches what the render
    pipeline expects. If/when shots support real video clips, switch to
    https://api.pexels.com/videos/search and adjust the caller in
    orchestrator.py to store type="video" on the Asset.

    Docs: https://www.pexels.com/api/documentation/
    """
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY is not set")

    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": api_key},
        params={"query": query, "per_page": 1, "orientation": orientation},
        timeout=15,
    )
    resp.raise_for_status()
    photos = resp.json().get("photos") or []
    if not photos:
        raise RuntimeError(f"No Pexels results for query: {query!r}")

    photo = photos[0]
    return {
        "provider": "pexels",
        "uri": photo["src"]["large2x"],
        "metadata": {
            "pexels_id": photo["id"],
            "photographer": photo.get("photographer"),
            "photographer_url": photo.get("photographer_url"),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "query": query,
        },
    }


def synthesize_speech(text: str, voice_id: str) -> str:
    """TODO: wire to ElevenLabs/Azure TTS. Returns audio asset URI."""
    raise NotImplementedError("Wire this to your TTS provider.")


def select_music_cue(mood: str, duration_ms: int) -> Dict[str, Any]:
    """TODO: wire to a licensed, mood-tagged music library (Soundstripe/Epidemic/Suno)."""
    raise NotImplementedError("Wire this to your music library provider.")
