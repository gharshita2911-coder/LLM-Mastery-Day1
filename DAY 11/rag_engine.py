"""
rag_engine.py
-------------
Core RAG pipeline:
  1. Retrieve top-K chunks via TF-IDF
  2. Call Groq LLM with a strict structured-output prompt
  3. Parse JSON from response
  4. Validate with Pydantic (RAGStructuredOutput)
  5. Retry up to MAX_RETRIES times on any failure
  6. Fallback to chunk-derived response if all retries fail

Requires:
    pip install groq pydantic
    export GROQ_API_KEY=gsk_...
"""

import json
import os
import sys
import time

from groq import Groq
from rag_schema import RAGStructuredOutput, SourceChunk
from retriever import retrieve

# ── Config ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL        = "llama3-8b-8192"
MAX_RETRIES  = 2          # retries after 1st attempt → 3 total attempts max
RETRY_DELAY  = 1.5        # seconds to wait between retries
TOP_K        = 3          # chunks retrieved per query

if not GROQ_API_KEY:
    print(
        "\n[ERROR] GROQ_API_KEY environment variable is not set.\n"
        "  Get a free key at: https://console.groq.com\n"
        "  Then run:  export GROQ_API_KEY=gsk_...\n",
        file=sys.stderr,
    )
    sys.exit(1)

_client = Groq(api_key=GROQ_API_KEY)

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a precise question-answering assistant.

You will receive:
  QUERY       - the user's question
  CONTEXT     - retrieved text chunks, each with a chunkId

Answer using ONLY the provided context. Respond with a single valid JSON
object and NOTHING ELSE (no markdown, no extra text, no code fences):

{
  "answer":     "<complete sentence(s) answering the query>",
  "confidence": "<high | medium | low>",
  "sources": [
    { "chunkId": "<id>", "snippet": "<15-60 word verbatim excerpt>" }
  ]
}

confidence rules:
  "high"   → 2+ chunks directly answer the query
  "medium" → 1 chunk supports it, or evidence is indirect
  "low"    → evidence is weak or only tangentially relevant

Include every chunkId you used. At least one source is required.
Output ONLY the JSON object — nothing else.
"""


def _build_user_message(query: str, chunks: list[dict]) -> str:
    ctx = "\n\n".join(f"[chunkId: {c['chunkId']}]\n{c['text']}" for c in chunks)
    return f"QUERY: {query}\n\nCONTEXT:\n{ctx}"


def _call_llm(user_msg: str) -> str:
    """Single Groq API call. Returns raw text."""
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.0,   # deterministic — maximises JSON compliance
        max_tokens=600,
    )
    return resp.choices[0].message.content.strip()


def _extract_json(raw: str) -> dict | None:
    """Extract a JSON dict from raw LLM output, handling common formatting issues."""
    # 1. Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 2. Strip markdown fences
    clean = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # 3. Find first {...} block
    s, e = raw.find("{"), raw.rfind("}") + 1
    if s != -1 and e > s:
        try:
            return json.loads(raw[s:e])
        except json.JSONDecodeError:
            pass
    return None


def _validate(data: dict) -> tuple[bool, RAGStructuredOutput | None, str]:
    """Validate a dict against the RAGStructuredOutput Pydantic schema."""
    try:
        obj = RAGStructuredOutput(**data)
        return True, obj, ""
    except Exception as exc:
        return False, None, str(exc)


def _build_fallback(query: str, chunks: list[dict]) -> RAGStructuredOutput:
    """
    Emergency fallback: construct a valid RAGStructuredOutput directly
    from retrieved chunk text. Always schema-valid; confidence is always 'low'.
    """
    combined = " ".join(c["text"] for c in chunks[:2])
    answer   = combined[:400] + ("..." if len(combined) > 400 else "")
    sources  = [
        SourceChunk(chunkId=c["chunkId"], snippet=c["text"][:150])
        for c in chunks[:2]
    ]
    return RAGStructuredOutput(answer=answer, confidence="low", sources=sources)


# ── Public API ─────────────────────────────────────────────────────────────────

def run_rag_query(query: str, top_k: int = TOP_K) -> dict:
    """
    Full RAG pipeline for one query.

    Returns:
    {
        "query":            str,
        "answer":           str,
        "confidence":       "high"|"medium"|"low",
        "sources":          [{ chunkId, snippet }],
        "valid":            bool,
        "attempts":         int,
        "used_fallback":    bool,
        "error":            str | None,
        "chunks_retrieved": [{ chunkId, doc, score }]
    }
    """
    chunks     = retrieve(query, top_k=top_k)
    user_msg   = _build_user_message(query, chunks)
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 2):   # 1, 2, 3
        try:
            raw    = _call_llm(user_msg)
            parsed = _extract_json(raw)

            if parsed is None:
                last_error = f"No JSON found in LLM response: {raw[:200]}"
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                continue

            ok, obj, err = _validate(parsed)
            if ok:
                return {
                    "query":            query,
                    "answer":           obj.answer,
                    "confidence":       obj.confidence,
                    "sources":          [s.model_dump() for s in obj.sources],
                    "valid":            True,
                    "attempts":         attempt,
                    "used_fallback":    False,
                    "error":            None,
                    "chunks_retrieved": [
                        {"chunkId": c["chunkId"], "doc": c["doc"], "score": c["score"]}
                        for c in chunks
                    ],
                }
            else:
                last_error = f"Schema validation failed: {err}"
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        except Exception as exc:
            last_error = str(exc)
            if attempt <= MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    # ── All attempts failed → fallback ─────────────────────────────────────────
    fb = _build_fallback(query, chunks)
    return {
        "query":            query,
        "answer":           fb.answer,
        "confidence":       fb.confidence,
        "sources":          [s.model_dump() for s in fb.sources],
        "valid":            True,   # fallback is always schema-valid
        "attempts":         MAX_RETRIES + 1,
        "used_fallback":    True,
        "error":            last_error,
        "chunks_retrieved": [
            {"chunkId": c["chunkId"], "doc": c["doc"], "score": c["score"]}
            for c in chunks
        ],
    }
