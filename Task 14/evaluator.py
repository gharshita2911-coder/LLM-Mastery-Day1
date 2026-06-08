"""
Evaluator — LLM-as-a-Judge for Retrieval Relevance & Faithfulness
==================================================================
Uses a separate, more capable Groq model to grade RAG outputs on:
  1. Retrieval Relevance: are the retrieved chunks relevant to the query?
  2. Faithfulness (No Hallucination): is the answer grounded in the chunks?
"""

import json
from typing import Optional

from groq import Groq

from config import GROQ_API_KEY, JUDGE_MODEL
from knowledge_base import get_all_chunks


# Build a lookup map for chunk texts (used to show evaluator the full context)
_KNOWLEDGE_MAP: dict[str, str] = {c["chunkId"]: c["text"] for c in get_all_chunks()}

# Initialise shared Groq client for grading
_CLIENT: Groq = Groq(api_key=GROQ_API_KEY)


# ── Grading prompt templates ──────────────────────────────────────────────────

_RELEVANCE_PROMPT_TPL: str = """You are an expert evaluator. Assess the relevance of the retrieved context chunks to the user's query.

Query: {query}

Retrieved Chunks:
{chunks_text}

Does the retrieved context contain information that is directly relevant to answering the user's query?
Respond with a single JSON object and NOTHING ELSE (no markdown, no code fences):
{{
  "relevant": true or false,
  "explanation": "concise explanation of why the context is or isn't relevant to the query"
}}"""

_FAITHFULNESS_PROMPT_TPL: str = """You are an expert evaluator. Assess the faithfulness (groundedness) of the generated answer compared to the retrieved context chunks.

Retrieved Chunks:
{chunks_text}

Generated Answer:
{answer}

Is the generated answer strictly grounded in the retrieved context chunks, without making any unsupported claims or hallucinating external facts?
Respond with a single JSON object and NOTHING ELSE (no markdown, no code fences):
{{
  "faithful": true or false,
  "explanation": "concise explanation of why the answer is or isn't faithful to the context"
}}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _call_judge(prompt: str) -> tuple[dict, int, int]:
    """
    Call the judge model and parse JSON response.

    Returns (parsed_data, prompt_tokens, completion_tokens).
    """
    resp = _CLIENT.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=300,
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content.strip()
    prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
    completion_tokens = resp.usage.completion_tokens if resp.usage else 0

    return json.loads(content), prompt_tokens, completion_tokens


def _format_chunks(chunks: list[dict]) -> str:
    """Format retrieved chunks for judge prompts."""
    parts: list[str] = []
    for c in chunks:
        chunk_text = _KNOWLEDGE_MAP.get(c["chunkId"], c.get("text", c.get("doc", "")))
        parts.append(f"Chunk [{c['chunkId']}]: {chunk_text}")
    return "\n\n".join(parts)


# ── Public API ────────────────────────────────────────────────────────────────

def grade_relevance(
    query: str,
    chunks: list[dict],
) -> tuple[bool, str, int, int]:
    """
    Grade retrieval relevance.

    Returns (relevant_ok, explanation, prompt_tokens, completion_tokens).
    """
    if not chunks:
        return False, "No chunks retrieved", 0, 0

    chunks_text = _format_chunks(chunks)
    prompt = _RELEVANCE_PROMPT_TPL.format(query=query, chunks_text=chunks_text)

    try:
        data, pt, ct = _call_judge(prompt)
        return bool(data.get("relevant", False)), data.get("explanation", ""), pt, ct
    except Exception as e:
        return False, f"Error during relevance grading: {e}", 0, 0


def grade_faithfulness(
    answer: str,
    chunks: list[dict],
) -> tuple[bool, str, int, int]:
    """
    Grade faithfulness / groundedness (no hallucination).

    Returns (faithful_ok, explanation, prompt_tokens, completion_tokens).
    """
    if not chunks:
        return False, "No chunks available to ground answer", 0, 0

    chunks_text = _format_chunks(chunks)
    prompt = _FAITHFULNESS_PROMPT_TPL.format(chunks_text=chunks_text, answer=answer)

    try:
        data, pt, ct = _call_judge(prompt)
        return bool(data.get("faithful", False)), data.get("explanation", ""), pt, ct
    except Exception as e:
        return False, f"Error during faithfulness grading: {e}", 0, 0
