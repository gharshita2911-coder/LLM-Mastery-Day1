"""
guardrails.py — RAG Engineering Phase 2
Guardrail module: input length limit, output schema validation,
retry logic with exponential backoff, and timeout handling.
"""

import asyncio
import json
import logging
import time
from typing import Any

import httpx

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
INPUT_MAX_CHARS: int = 8_000
REQUEST_TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3           # up to 3 attempts total (1 original + 2 retries)
BACKOFF_BASE: float = 1.0      # seconds; doubles each retry

# Expected output schema keys
REQUIRED_SCHEMA_KEYS: list[str] = ["answer", "sources"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("guardrails")


# ─────────────────────────────────────────────
# Custom Exceptions
# ─────────────────────────────────────────────
class InputTooLongError(ValueError):
    """Raised when the input exceeds the character limit."""


class OutputSchemaError(ValueError):
    """Raised when the LLM response fails schema validation."""


class UpstreamTimeoutError(TimeoutError):
    """Raised when the upstream LLM call times out."""


class UpstreamError(RuntimeError):
    """Raised for non-retryable upstream errors (4xx except 429)."""


# ─────────────────────────────────────────────
# 1. Input Length Guard
# ─────────────────────────────────────────────
def validate_input_length(text: str, max_chars: int = INPUT_MAX_CHARS) -> None:
    """
    Raise InputTooLongError (HTTP 400 equivalent) if *text* exceeds *max_chars*.
    Call this before any LLM/embedding call.
    """
    if len(text) > max_chars:
        raise InputTooLongError(
            f"Input length {len(text):,} chars exceeds limit of {max_chars:,} chars."
        )


# ─────────────────────────────────────────────
# 2. Output Schema Validator
# ─────────────────────────────────────────────
SAFE_FALLBACK: dict = {
    "answer": "I'm sorry, I could not produce a valid response at this time.",
    "sources": [],
    "_fallback": True,
}


def validate_output_schema(raw: str) -> dict:
    """
    Parse *raw* JSON string and assert required keys are present.
    Returns the parsed dict on success.
    Raises OutputSchemaError on failure so the caller can retry or fall back.
    Never returns unparsed / invalid JSON.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OutputSchemaError(f"JSON parse failed: {exc}") from exc

    if not isinstance(data, dict):
        raise OutputSchemaError(f"Expected a JSON object, got {type(data).__name__}.")

    missing = [k for k in REQUIRED_SCHEMA_KEYS if k not in data]
    if missing:
        raise OutputSchemaError(f"Missing required keys: {missing}")

    return data


# ─────────────────────────────────────────────
# 3 & 4. Retry + Timeout — core HTTP helper
# ─────────────────────────────────────────────
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


async def _call_llm_api(
    client: httpx.AsyncClient,
    payload: dict,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> str:
    """
    Raw async call to the LLM API.
    Returns the model's text response (content[0].text for Anthropic-style APIs).
    Raises:
        UpstreamTimeoutError  — request timed out
        UpstreamError         — non-retryable 4xx
        httpx.HTTPStatusError — retryable 5xx / 429 (caller handles retry)
    """
    try:
        response = await client.post(
            "/v1/messages",
            json=payload,
            timeout=timeout,
        )
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        raise UpstreamTimeoutError("LLM request timed out.") from exc

    if response.status_code == 200:
        data = response.json()
        # Support both Anthropic-style and OpenAI-style response shapes
        if "content" in data:
            blocks = data["content"]
            text_blocks = [b["text"] for b in blocks if b.get("type") == "text"]
            return "\n".join(text_blocks)
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        raise OutputSchemaError("Unrecognised API response shape.")

    # 4xx (except 429): do NOT retry
    if 400 <= response.status_code < 500 and response.status_code != 429:
        raise UpstreamError(
            f"Non-retryable upstream error {response.status_code}: {response.text[:200]}"
        )

    # 429 / 5xx: raise so retry loop can catch it
    response.raise_for_status()
    return ""   # unreachable; satisfies type checker


async def call_llm_with_retries(
    client: httpx.AsyncClient,
    payload: dict,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    max_retries: int = MAX_RETRIES,
    backoff_base: float = BACKOFF_BASE,
) -> str:
    """
    Wraps *_call_llm_api* with exponential-backoff retry logic.

    Retry policy:
        • Retries on httpx.HTTPStatusError (429 / 5xx) up to *max_retries* times.
        • Exponential backoff: wait = backoff_base * 2^attempt  (1 s, 2 s, 4 s …)
        • Does NOT retry on 4xx (UpstreamError) or timeouts (UpstreamTimeoutError).

    Returns the raw LLM text string.
    """
    last_exc: Exception = RuntimeError("Unknown error")

    for attempt in range(max_retries):
        try:
            return await _call_llm_api(client, payload, timeout=timeout)

        except (UpstreamTimeoutError, UpstreamError):
            raise  # non-retryable — propagate immediately

        except (httpx.HTTPStatusError, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = backoff_base * (2 ** attempt)
                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                    attempt + 1, max_retries, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("All %d attempts exhausted.", max_retries)

    raise last_exc


# ─────────────────────────────────────────────
# 5. Main guarded RAG endpoint handler
# ─────────────────────────────────────────────
async def rag_query(
    query: str,
    context: str,
    client: httpx.AsyncClient,
    *,
    system_prompt: str = (
        "You are a helpful assistant. "
        'Always respond with valid JSON matching {"answer": "...", "sources": [...]}.'
    ),
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """
    Full guarded RAG query pipeline. Returns a dict with keys:
        status  : "ok" | "error"
        code    : HTTP-equivalent status code (int)
        data    : validated output dict (on success or fallback)
        message : human-readable description
        meta    : timing / retry metadata
    """
    start = time.monotonic()
    meta: dict[str, Any] = {"attempts": 0, "fallback_used": False}

    # ── Guard 1: input length ──────────────────────────────────────────────
    full_input = f"{system_prompt}\n\nContext:\n{context}\n\nQuery:\n{query}"
    try:
        validate_input_length(full_input)
    except InputTooLongError as exc:
        return {
            "status": "error",
            "code": 400,
            "data": None,
            "message": str(exc),
            "meta": {**meta, "elapsed": time.monotonic() - start},
        }

    # ── Guards 2–4: LLM call with retry + timeout ─────────────────────────
    payload = {
        "model": model,
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuery:\n{query}",
            }
        ],
    }

    raw_text: str | None = None
    try:
        raw_text = await call_llm_with_retries(client, payload)
        meta["attempts"] = 1  # simplified; real impl tracks per-attempt
    except UpstreamTimeoutError as exc:
        return {
            "status": "error",
            "code": 504,
            "data": None,
            "message": f"Gateway timeout: {exc}",
            "meta": {**meta, "elapsed": time.monotonic() - start},
        }
    except UpstreamError as exc:
        return {
            "status": "error",
            "code": 502,
            "data": None,
            "message": f"Upstream error: {exc}",
            "meta": {**meta, "elapsed": time.monotonic() - start},
        }
    except Exception as exc:
        return {
            "status": "error",
            "code": 503,
            "data": None,
            "message": f"Service unavailable: {exc}",
            "meta": {**meta, "elapsed": time.monotonic() - start},
        }

    # ── Guard 2: output schema validation (retry once on failure) ─────────
    validated: dict | None = None
    for schema_attempt in range(2):   # try original + one retry
        try:
            validated = validate_output_schema(raw_text)
            break
        except OutputSchemaError as exc:
            logger.warning("Schema validation failed (attempt %d): %s", schema_attempt + 1, exc)
            if schema_attempt == 0:
                # Retry the LLM call once
                try:
                    raw_text = await call_llm_with_retries(client, payload)
                except Exception:
                    break   # give up; fall through to safe fallback
            else:
                break

    if validated is None:
        logger.error("Schema validation failed after retry — using safe fallback.")
        validated = {**SAFE_FALLBACK}
        meta["fallback_used"] = True

    meta["elapsed"] = time.monotonic() - start
    return {
        "status": "ok",
        "code": 200,
        "data": validated,
        "message": "Success" + (" (fallback)" if meta["fallback_used"] else ""),
        "meta": meta,
    }


# ─────────────────────────────────────────────
# Factory: build a pre-configured httpx client
# ─────────────────────────────────────────────
def build_client(base_url: str, api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
