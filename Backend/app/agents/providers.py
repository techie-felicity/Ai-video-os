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
from typing import Any, Dict

from openai import OpenAI, RateLimitError, APIStatusError

logger = logging.getLogger(__name__)

_client = None


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def _extract_retry_seconds(err: Exception, default: float = 5.0) -> float:
    """
    Groq's 429 body includes a hint like 'Please try again in 18.125s'.
    Pull that out if present, otherwise fall back to a default wait.
    """
    message = str(err)
    match = re.search(r"try again in ([\d.]+)s", message)
    if match:
        try:
            return float(match.group(1)) + 0.5  # small buffer
        except ValueError:
            pass
    return default


def call_reasoning_model(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.3-70b-versatile",
    max_retries: int = 4,
) -> Dict[str, Any]:
    """
    Used by ScriptAgent, EditorAgent, StoryboardAgent, VisualAgent for structured
    JSON reasoning. Expects the model to return ONLY JSON (enforced via prompt).

    Retries on rate limits (429) using the wait time Groq suggests in the
    error message, with exponential backoff as a fallback if that's absent.
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


def search_stock_footage(query: str) -> Dict[str, Any]:
    """TODO: wire to Pexels/Storyblocks API. Returns asset metadata + URI."""
    raise NotImplementedError("Wire this to a licensed stock footage provider.")


def synthesize_speech(text: str, voice_id: str) -> str:
    """TODO: wire to ElevenLabs/Azure TTS. Returns audio asset URI."""
    raise NotImplementedError("Wire this to your TTS provider.")


def select_music_cue(mood: str, duration_ms: int) -> Dict[str, Any]:
    """TODO: wire to a licensed, mood-tagged music library (Soundstripe/Epidemic/Suno)."""
    raise NotImplementedError("Wire this to your music library provider.")
