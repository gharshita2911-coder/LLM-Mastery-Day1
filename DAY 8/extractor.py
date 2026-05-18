"""
extractor.py - Step 1: Extract
================================
Calls Gemini and returns a structured dict with:
  person   - reporter full name (or null)
  company  - reporter company / org (or null)
  product  - product / service name (or null)
  issue    - concise problem phrase (max 10 words)

Also returns token usage from Gemini's usage_metadata.
Raises ValueError if the response can't be parsed or 'issue' is missing.
"""

import json
import re

from config import CLIENT, Completion,MODEL


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """
Extract structured data from this support ticket.

Return ONLY a raw JSON object (no markdown, no code fences)
with these keys:

person   - reporter name or null
company  - reporter company or organization or null
product  - product/service name or null
issue    - concise phrase describing the core problem (max 10 words)

Prefer actual software/product names over generic terms like API or app.
Ticket:
\"\"\"{text}\"\"\"
"""


# ---------------------------------------------------------------------------
# Step function
# ---------------------------------------------------------------------------

def step1_extract(text: str) -> tuple[dict, Completion]:
    """
    Returns:
        extracted (dict)   - person, company, product, issue
        completion         - token usage for this call
    """

    response = CLIENT.chat.completions.create(
        model=MODEL,
        messages=[
        {
            "role": "user",
            "content": _EXTRACT_PROMPT.format(text=text)
        }
        ],
    temperature=0,)

    # Token usage
    meta = response.usage

    completion = Completion(
        prompt_token_count=getattr(meta, "prompt_token_count", 0),
        candidates_token_count=getattr(meta, "candidates_token_count", 0),
        total_token_count=getattr(meta, "total_token_count", 0),
    )

    # Raw model output
    raw = response.choices[0].message.content.strip()

    # Remove markdown code fences
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Parse JSON
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Invalid JSON returned by Gemini: {exc}")

    # Validate object
    if not isinstance(parsed, dict):
        raise ValueError("Gemini response is not a JSON object")

    # Required field
    if not parsed.get("issue"):
        raise ValueError("Gemini did not return required field 'issue'")

    extracted = {
        "person": parsed.get("person") or None,
        "company": parsed.get("company") or None,
        "product": parsed.get("product") or None,
        "issue": parsed.get("issue"),
    }

    return extracted, completion