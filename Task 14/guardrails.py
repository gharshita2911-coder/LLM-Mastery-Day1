"""
Guardrails — Output Validation, Confidence Scoring & Fallback Handling
======================================================================
Ensures that RAG responses meet the expected schema and quality standards.
Implements confidence classification, schema validation, and fallback logic.
"""

import json
import re
from typing import Any, Optional


# ── Schema definition ─────────────────────────────────────────────────────────

EXPECTED_SCHEMA: dict[str, str] = {
    "answer": "str — non-empty answer string",
    "confidence": "'high' | 'medium' | 'low'",
    "sources": "list[dict] — each with chunkId, snippet, category",
}

VALID_CONFIDENCE_LEVELS: frozenset = frozenset({"high", "medium", "low"})


# ── Validation ────────────────────────────────────────────────────────────────

def validate_response(response: dict) -> tuple[bool, str]:
    """
    Validate a parsed RAG response against the expected schema.

    Returns (is_valid, error_message).
    """
    # Must be a dict
    if not isinstance(response, dict):
        return False, "Response is not a dict"

    # Must have 'answer' — non-empty string
    answer = response.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return False, "Missing or empty 'answer' field"

    # Must have 'confidence' — valid level
    confidence = response.get("confidence")
    if confidence not in VALID_CONFIDENCE_LEVELS:
        return False, (
            f"Invalid confidence '{confidence}'. "
            f"Must be one of {sorted(VALID_CONFIDENCE_LEVELS)}"
        )

    # Must have 'sources' — non-empty list of dicts
    sources = response.get("sources")
    if not isinstance(sources, list) or len(sources) == 0:
        return False, "Missing or empty 'sources' list"

    for src in sources:
        if not isinstance(src, dict):
            return False, "Source entry is not a dict"
        if "chunkId" not in src:
            return False, "Source entry missing 'chunkId'"

    return True, ""


# ── Confidence scoring ────────────────────────────────────────────────────────

def compute_confidence(
    similarity_scores: list[float],
    num_attempts: int,
    validation_passed: bool,
    used_fallback: bool,
) -> str:
    """
    Determine confidence level based on retrieval quality, attempts, and status.

    Uses the MAX (top-1) similarity score rather than average, since TF-IDF
    cosine similarities are typically in the 0.2-0.6 range and the top chunk
    is the most indicative of retrieval quality.

    Rules:
      - high:   max similarity >= 0.4, first attempt, validation passed, no fallback
      - medium: max similarity >= 0.2, <= 2 attempts, validation passed
      - low:    otherwise or fallback used
    """
    max_sim = max(similarity_scores) if similarity_scores else 0.0

    if (
        max_sim >= 0.4
        and num_attempts == 1
        and validation_passed
        and not used_fallback
    ):
        return "high"

    if max_sim >= 0.2 and num_attempts <= 2 and validation_passed:
        return "medium"

    return "low"


# ── JSON extraction (some models wrap JSON in markdown fences) ────────────────

def extract_json(text: str) -> Optional[dict]:
    """
    Extract a JSON object from LLM output, handling markdown fences.

    Returns parsed dict or None on failure.
    """
    # Try to find JSON between triple backticks
    fence_pattern = r"```(?:json)?\s*\n?(\{.*?\})\n?\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to parse the whole response as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object anywhere in the text
    obj_pattern = r"(\{.*\})"
    match = re.search(obj_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


# ── Build a safe fallback response ────────────────────────────────────────────

def build_fallback_response(query: str, chunks: list[dict]) -> dict:
    """
    Build a minimal valid response when all attempts fail.
    Uses the highest-scoring chunk text as a base answer.
    """
    answer = (
        "I'm unable to generate a confident answer at this time. "
        "Based on available information, please refer to the retrieved "
        "context chunks below for relevant details."
    )

    sources = [
        {"chunkId": c["chunkId"], "snippet": c.get("text", c.get("doc", ""))[:120]}
        for c in chunks
    ]

    return {
        "answer": answer,
        "confidence": "low",
        "sources": sources,
    }
