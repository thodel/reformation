#!/usr/bin/env python3
"""Shared access to the Gemini API for the recognition and translation pipelines.

Wraps the google-genai SDK with the things every caller here needs: a client
built from the environment, retry with backoff on transient failures, and
sanitising of the model's conversational scaffolding.

The scaffolding matters. 669 of the repository's translation files had to be
repaired because a preamble like "Hier ist die Übersetzung ...:" was written
straight into the published text (see scripts/clean_translations.py, which
repairs the historical files). New output is cleaned at the source instead.
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:  # pragma: no cover - exercised only without the SDK
    genai = None
    types = None

# Confirmed callable against this project's key on 2026-08-19 via --list-models
# AND an actual generate call. models.list() is not sufficient on its own:
# gemini-2.5-pro is listed but returns 404 NOT_FOUND for generateContent, so a
# default taken from the listing alone would fail every page of a full run.
DEFAULT_MODEL = "gemini-3.1-pro-preview"

ENV_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

# Lines the model prepends to introduce what it is about to output. Matched only
# at the very start of a response, never inside the body.
_OPENER = r"(?:absolut|okay|ok|gerne|klar|natürlich|sicher|selbstverständlich)\s*[!,.]?\s*"
_ANNOUNCE = (
    r"(?:hier\s+(?:ist|folgt|kommt|sind)?\s*(?:die|der|das)?\s*"
    r"(?:übersetzung|transkription|transkribierte|erkannte|text)"
    r"|(?:die|der)\s+(?:übersetzung|transkription)\s+(?:lautet|folgt))"
)
PREAMBLE_RE = re.compile(rf"^\s*(?:{_OPENER})?{_ANNOUNCE}\b.*$", re.IGNORECASE)
FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*$")
LABEL_RE = re.compile(r"^\s*(?:text|original|transkription|übersetzung)\s*:\s*$", re.IGNORECASE)

RETRYABLE = (
    "429", "500", "502", "503", "504",
    "deadline", "timeout", "unavailable", "overloaded",
    # Long image requests get dropped mid-flight; observed as
    # "RemoteProtocolError: Server disconnected" after ~257s on 2 of 16 sample
    # pages. These are transient and must be retried, not surfaced as failures.
    "disconnect", "connection reset", "connection aborted", "protocolerror",
    "incompleteread", "incomplete read", "broken pipe", "eof occurred",
)


class GeminiUnavailable(RuntimeError):
    """The SDK is missing or no API key is configured."""


@dataclass
class Usage:
    calls: int = 0
    failures: int = 0


def api_key_from_env() -> str:
    for name in ENV_KEYS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def build_client() -> Any:
    if genai is None:
        raise GeminiUnavailable(
            "google-genai is not installed. Run: pip install google-genai"
        )
    key = api_key_from_env()
    if not key:
        raise GeminiUnavailable(
            f"No API key. Set one of: {', '.join(ENV_KEYS)}"
        )
    return genai.Client(api_key=key)


def list_models(client: Any) -> list[str]:
    """Model ids the configured key may call, for confirming a default."""
    names = []
    for model in client.models.list():
        name = getattr(model, "name", "") or ""
        actions = getattr(model, "supported_actions", None) or []
        if actions and "generateContent" not in actions:
            continue
        names.append(name.removeprefix("models/"))
    return sorted(names)


def strip_scaffolding(text: str) -> str:
    """Remove conversational wrapping the model added around its answer."""
    lines = (text or "").strip().splitlines()

    while lines and (not lines[0].strip() or FENCE_RE.match(lines[0])):
        lines.pop(0)
    if lines and PREAMBLE_RE.match(lines[0]):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and LABEL_RE.match(lines[0]):
            lines.pop(0)
    while lines and (not lines[-1].strip() or FENCE_RE.match(lines[-1])):
        lines.pop()

    return "\n".join(lines).strip()


def is_retryable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in RETRYABLE)


def generate(
    client: Any,
    *,
    model: str,
    parts: list[Any],
    system_instruction: str | None = None,
    temperature: float = 0.0,
    max_retries: int = 4,
    usage: Usage | None = None,
) -> str:
    """Call the model, retrying transient failures, and return cleaned text."""
    config = None
    if types is not None:
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
        )

    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            if usage:
                usage.calls += 1
            response = client.models.generate_content(
                model=model, contents=parts, config=config
            )
            return strip_scaffolding(getattr(response, "text", "") or "")
        except Exception as exc:  # noqa: BLE001 - SDK raises a wide range
            last = exc
            if usage:
                usage.failures += 1
            if not is_retryable(exc) or attempt == max_retries - 1:
                raise
            # Exponential backoff with jitter, so a rate limit does not turn
            # into a synchronised retry storm across pages.
            time.sleep(min(2**attempt + random.random(), 30))
    raise last if last else RuntimeError("generate failed")


def image_part(data: bytes, mime_type: str = "image/jpeg") -> Any:
    if types is None:
        raise GeminiUnavailable("google-genai is not installed")
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def text_part(text: str) -> Any:
    if types is None:
        raise GeminiUnavailable("google-genai is not installed")
    return types.Part.from_text(text=text)
