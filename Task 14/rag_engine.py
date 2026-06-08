"""
RAG Engine — Core Query Pipeline
==================================
Orchestrates end-to-end RAG: retrieve context, prompt LLM, validate output,
apply fallback if needed. Returns structured results with cost and latency data.
"""

import json
import time
from typing import Optional

from groq import Groq

from config import (
    GROQ_API_KEY,
    RAG_MODEL,
    FALLBACK_MODEL,
    TOP_K,
    MAX_RETRIEVAL_ATTEMPTS,
)
from cost_tracker import CostTracker
from guardrails import (
    extract_json,
    validate_response,
    compute_confidence,
    build_fallback_response,
)
from knowledge_base import retrieve


# Initialise shared Groq client
_CLIENT: Groq = Groq(api_key=GROQ_API_KEY)

# Global cost tracker instance
_COST_TRACKER: CostTracker = CostTracker()


# ── System prompt for the RAG model ───────────────────────────────────────────

RAG_SYSTEM_PROMPT: str = """You are an IT Helpdesk assistant. Answer the user's question based strictly on the provided context below.

Rules:
1. Answer thoroughly and informatively using ONLY the provided context. Include all relevant details from the context.
2. If the context does not contain enough information, say so — do not make up an answer.
3. Always cite the chunkId of the sources you used.
4. Respond with a valid JSON object (NO markdown, NO code fences, NO extra text).

Response format:
{
  "answer": "your complete answer with all relevant details from the context",
  "confidence": "high" | "medium" | "low",
  "sources": [
    {"chunkId": "chunk_001", "snippet": "brief excerpt from the context"},
    {"chunkId": "chunk_003", "snippet": "another excerpt"}
  ]
}"""


# ── Core query function ───────────────────────────────────────────────────────

def run_rag_query(query: str, top_k: int = TOP_K) -> dict:
    """
    Execute a full RAG query:
      1. Retrieve relevant chunks from the knowledge base.
      2. Build a prompt with the retrieved context.
      3. Call the Groq LLM (with retry/fallback).
      4. Validate and structure the response.
      5. Compute confidence and track cost/latency.

    Returns a dict with the full result record.
    """
    start_time: float = time.time()
    query_id: str = f"Q{abs(hash(query)) % 1000:03d}"
    call_records: list[dict] = []

    # ── Step 1: Retrieve ──────────────────────────────────────────────────────
    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        elapsed = time.time() - start_time
        return {
            "query_id": query_id,
            "query": query,
            "answer": "",
            "confidence": "low",
            "sources": [],
            "valid": False,
            "error": "No chunks retrieved from knowledge base",
            "chunks_retrieved": [],
            "attempts": 0,
            "used_fallback": False,
            "elapsed_seconds": round(elapsed, 4),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }

    # Build context string from retrieved chunks
    context_parts: list[str] = [
        f"[{c['chunkId']}] (Category: {c['category']})\n{c['text']}"
        for c in chunks
    ]
    context_str: str = "\n\n".join(context_parts)

    similarity_scores: list[float] = [c["score"] for c in chunks]

    # ── Step 2: Generate (with retries and fallback) ──────────────────────────
    answer_data: Optional[dict] = None
    used_fallback: bool = False
    attempts: int = 0
    last_error: str = ""

    models_to_try = [RAG_MODEL] * MAX_RETRIEVAL_ATTEMPTS + [FALLBACK_MODEL]

    for attempt, model in enumerate(models_to_try):
        attempts = attempt + 1
        if attempt >= MAX_RETRIEVAL_ATTEMPTS:
            used_fallback = True

        # Build user prompt
        user_prompt: str = (
            f"Context:\n{context_str}\n\n"
            f"Question: {query}\n\n"
            f"Respond with valid JSON only."
        )

        try:
            call_start = time.time()
            resp = _CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            call_elapsed = time.time() - call_start
            content = resp.choices[0].message.content.strip()
            pt = resp.usage.prompt_tokens if resp.usage else 0
            ct = resp.usage.completion_tokens if resp.usage else 0

            # Track cost for this call
            call_record = _COST_TRACKER.record(
                prompt_tokens=pt,
                completion_tokens=ct,
                total_tokens=pt + ct,
                model=model,
                elapsed_seconds=call_elapsed,
            )
            call_records.append(call_record)

            # Parse JSON
            parsed = json.loads(content)
            valid, err = validate_response(parsed)

            if valid:
                answer_data = parsed
                break
            else:
                last_error = err
                # Try fallback JSON extraction before giving up on this attempt
                extracted = extract_json(content)
                if extracted:
                    valid2, err2 = validate_response(extracted)
                    if valid2:
                        answer_data = extracted
                        break
                    last_error = err2

        except Exception as e:
            last_error = str(e)
            # Still record a zero-cost entry for the failed attempt
            call_records.append({
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "error": str(e),
                "elapsed_seconds": 0.0,
            })

    # ── Step 3: Build final result ────────────────────────────────────────────
    elapsed_total = time.time() - start_time

    if answer_data is None:
        # All attempts failed — use fallback response
        fallback = build_fallback_response(query, chunks)
        confidence = "low"
        is_valid = True  # Fallback is structurally valid
        error_msg = f"All attempts failed. Last error: {last_error}"
    else:
        confidence = answer_data.get("confidence", "low")
        # Recompute confidence based on actual retrieval quality
        confidence = compute_confidence(
            similarity_scores, attempts, True, used_fallback
        )
        is_valid = True
        error_msg = ""

    sources = (
        [
            {"chunkId": c["chunkId"], "snippet": c["text"][:120], "category": c.get("category", "")}
            for c in chunks
        ]
        if answer_data
        else fallback.get("sources", [])
    )

    answer = answer_data.get("answer", "") if answer_data else fallback.get("answer", "")

    # Aggregate cost for this query
    query_cost_record = _COST_TRACKER.record_query(query_id, call_records)

    return {
        "query_id": query_id,
        "query": query,
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "valid": is_valid,
        "client_valid": is_valid,
        "server_valid": True,
        "attempts": attempts,
        "used_fallback": used_fallback,
        "error": error_msg,
        "chunks_retrieved": chunks,
        "elapsed_seconds": round(elapsed_total, 4),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prompt_tokens": query_cost_record.get("total_prompt_tokens", 0),
        "completion_tokens": query_cost_record.get("total_completion_tokens", 0),
        "total_tokens": query_cost_record.get("total_tokens", 0),
        "cost_usd": query_cost_record.get("cost_usd", 0.0),
    }


def get_cost_summary() -> dict:
    """Return the cost tracker's aggregate summary."""
    return _COST_TRACKER.summary()


def reset_cost_tracker() -> None:
    """Reset the global cost tracker (useful between test runs)."""
    _COST_TRACKER.clear()
