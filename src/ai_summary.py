"""AI plain-language summaries. Provider-specific code lives ONLY in _call_model()."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_MODEL = "gpt-4o-mini"  # single place for the fallback; override with OPENAI_MODEL

SYSTEM_INSTRUCTIONS = """You explain water-quality dashboard results to people with no technical background.
Rules:
- Use ONLY the JSON facts provided. Do not invent measurements, sources, thresholds, causes or conclusions.
- All numbers and statuses were computed by software. Repeat them; never recalculate or change them.
- If data_is_synthetic_demo is true, say clearly that this is made-up demonstration data, not real observations.
- Never say water is safe or unsafe. A reading inside or outside a reference range is not a safety verdict.
- Mention thresholds only with their stated reference name, unit and source. If a threshold is labelled
  illustrative or unverified, say so.
- Do not give medical, health or environmental claims. Do not speculate about causes.
- If data is too limited for a conclusion (few points, few dates, missing values), say so plainly.
- Use short sentences and plain words. Structure with these headings:
  What this data shows / Main observations / Readings outside the reference range / Trends and regional differences /
  Missing data and unavailable thresholds / Limitations / Sensible next steps.
- Next steps must be modest, e.g. re-testing, checking the data source, or consulting local water authorities."""


@dataclass
class AIResult:
    text: str | None = None
    error: str | None = None


def get_ai_config(get_secret=os.getenv) -> tuple[str | None, str]:
    """(api_key, model). get_secret is injectable so the app can also read Streamlit secrets."""
    return get_secret("OPENAI_API_KEY") or None, get_secret("OPENAI_MODEL") or DEFAULT_MODEL


def _call_model(payload: dict, api_key: str, model: str, timeout: float) -> str:
    from openai import OpenAI  # imported lazily so the dashboard runs without the SDK being used

    client = OpenAI(api_key=api_key, timeout=timeout, max_retries=1)
    resp = client.responses.create(model=model, instructions=SYSTEM_INSTRUCTIONS,
                                   input="Explain these dashboard results:\n" + json.dumps(payload, default=str))
    return resp.output_text


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__  # never include str(exc): it could echo request details
    if name in ("AuthenticationError", "PermissionDeniedError"):
        return "The AI provider rejected the API key. Check OPENAI_API_KEY."
    if name == "RateLimitError":
        return "The AI provider rate limit or quota was reached. Wait a moment and try again."
    if name in ("APITimeoutError", "Timeout", "TimeoutError"):
        return "The AI provider took too long to respond. Try again."
    if name == "APIConnectionError":
        return "Could not connect to the AI provider. Check your internet connection."
    if name == "NotFoundError":
        return "The configured model was not found. Check OPENAI_MODEL."
    return f"The AI summary could not be generated ({name}). The rest of the dashboard is unaffected."


def generate_summary(payload: dict, api_key: str | None, model: str, timeout: float = 45.0) -> AIResult:
    if not api_key:
        return AIResult(error="No API key configured. Set OPENAI_API_KEY (see README).")
    try:
        text = _call_model(payload, api_key, model, timeout)
    except Exception as exc:  # deliberately broad: any failure becomes a safe message
        return AIResult(error=_friendly_error(exc))
    if not text or not text.strip():
        return AIResult(error="The AI provider returned an empty response.")
    return AIResult(text=text.strip())
