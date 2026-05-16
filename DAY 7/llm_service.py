# src/llm_service.py
# Handles all Gemini API interactions for lead analysis

import json
import os
import re

import google.generativeai as genai

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]

API_KEYS = [key for key in API_KEYS if key]  # filter out None values
SYSTEM_PROMPT = """You are an expert CRM analyst. When given a lead's name, company, and notes,
you analyze the information and return ONLY a valid JSON object — no markdown, no explanation, no extra text.

The JSON must have exactly these three fields:
- summary: string (2-3 sentences summarizing the lead's situation and key points)
- suggestedFollowUp: string (one concrete, actionable follow-up step with a specific timeframe)
- sentimentScore: string (exactly one of: "positive", "neutral", or "negative")

Sentiment scoring guide:
- positive: lead shows strong interest, enthusiasm, urgency, or clear buying signals
- neutral: lead is exploring, non-committal, or sending mixed signals
- negative: lead shows disinterest, objections, budget freeze, or is unlikely to convert"""

VALID_SCORES = {"positive", "neutral", "negative"}

def generate_with_fallback(prompt:str):
    last_error = None
    for api_key in API_KEYS:
        try:
           genai.configure(api_key=api_key)
           model=genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_PROMPT)
           response = model.generate_content(prompt)
           return response.text
        
        except Exception as e:
            print(f"API Key failed: {api_key[:4]}... Error: {e}")
            last_error = e

    raise ValueError("All API keys failed.") from last_error

def analyze_lead(name: str, company: str, notes: str) -> dict:
    """
    Analyze a CRM lead using a single Gemini API call.

    Args:
        name:    Lead's full name
        company: Lead's company
        notes:   Sales notes about the lead

    Returns:
        dict with keys: summary, suggestedFollowUp, sentimentScore

    Raises:
        ValueError: If the LLM returns malformed or invalid output
        Exception:  For Gemini API errors (propagated to caller)
    """
    prompt = f"""Analyze this CRM lead and return a JSON object only:

Name: {name}
Company: {company}
Notes: {notes}"""

    raw_text = generate_with_fallback(prompt).strip()

    # Strip accidental markdown fences (```json ... ```)
    clean = re.sub(r"```(?:json)?|```", "", raw_text).strip()

    # Parse JSON
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini returned non-JSON output: {raw_text[:200]}"
        ) from e

    # Validate required fields
    for field in ("summary", "suggestedFollowUp", "sentimentScore"):
        if not isinstance(parsed.get(field), str) or not parsed[field].strip():
            raise ValueError(f"Missing or invalid field in LLM response: '{field}'")

    if parsed["sentimentScore"] not in VALID_SCORES:
        raise ValueError(f"sentimentScore must be one of {VALID_SCORES}, got: '{parsed['sentimentScore']}'" )

    return {
        "summary": parsed["summary"],
        "suggestedFollowUp": parsed["suggestedFollowUp"],
        "sentimentScore": parsed["sentimentScore"],
    }
