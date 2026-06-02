"""
RAG Query Pipeline
==================
Phase 2 – RAG Engineering | Owner: Both

Query flow: Question → Embed → Cosine similarity search → Top-K context → Groq LLM → Answer
Results stored in data/query_results.json

Env vars required:
  GROQ_API_KEY    – your Groq API key
  INDEX_PATH      – path to the JSON index          (default: data/index.json)
  TOP_K           – number of chunks to retrieve    (default: 5)
  GROQ_MODEL      – Groq chat model to use          (default: llama3-70b-8192)
  RESULT_PATH     – where to append query results   (default: data/query_results.json)
"""

import os
import json
import math
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from sentence_transformers import SentenceTransformer
from groq import Groq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/query.log"),
    ],
)
log = logging.getLogger("rag.query")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
INDEX_PATH   = Path(os.getenv("INDEX_PATH",   "data/index.json"))
RESULT_PATH  = Path(os.getenv("RESULT_PATH",  "data/query_results.json"))
TOP_K        = int(os.getenv("TOP_K", 5))
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama3-70b-8192")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

SYSTEM_PROMPT = """\
You are a precise and helpful assistant. Answer the user's question using ONLY
the context passages provided. If the context does not contain enough information,
say "I don't have enough context to answer that." Do not fabricate facts.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_embed_cache: Optional[SentenceTransformer] = None

def get_embed_model() -> SentenceTransformer:
    global _embed_cache
    if _embed_cache is None:
        log.info("Loading embedding model: %s", EMBED_MODEL)
        _embed_cache = SentenceTransformer(EMBED_MODEL)
    return _embed_cache


def load_index() -> dict:
    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            f"Index not found at {INDEX_PATH}. Run indexer.py first."
        )
    with INDEX_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def append_result(result: dict) -> None:
    """Append a single query result to the rolling JSON results file."""
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if RESULT_PATH.exists():
        with RESULT_PATH.open("r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []
    history.append(result)
    with RESULT_PATH.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    log.info("Result appended → %s  (total stored: %d)", RESULT_PATH, len(history))


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embed the query and return the top-K most similar chunks from the index.

    Returns
    -------
    list of chunk dicts sorted by similarity descending, each with a
    'similarity' field added.
    """
    index  = load_index()
    chunks = index.get("chunks", [])
    if not chunks:
        raise ValueError("Index is empty. Please index some documents first.")

    model   = get_embed_model()
    q_vec   = model.encode([query], convert_to_numpy=True)[0].tolist()

    scored = []
    for chunk in chunks:
        sim = _cosine_similarity(q_vec, chunk["embedding"])
        scored.append({**chunk, "similarity": round(sim, 6)})

    scored.sort(key=lambda c: c["similarity"], reverse=True)
    top = scored[:top_k]
    log.info("Retrieved %d chunks (top similarity: %.4f)", len(top), top[0]["similarity"] if top else 0)
    return top


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_answer(question: str, context_chunks: list[dict]) -> dict:
    """
    Call Groq LLM with the retrieved context and return a structured response.

    Returns
    -------
    dict with keys: answer, model, prompt_tokens, completion_tokens, latency_s
    """
    if not GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    context_text = "\n\n---\n\n".join(
        f"[Source: {c['source']} | chunk {c['chunk_idx']}]\n{c['text']}"
        for c in context_chunks
    )

    user_message = f"""Context passages:
{context_text}

Question: {question}

Answer:"""

    client = Groq(api_key=GROQ_API_KEY)

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    latency = round(time.perf_counter() - t0, 3)

    answer = response.choices[0].message.content.strip()
    usage  = response.usage

    log.info(
        "LLM response received | model=%s | tokens=%d+%d | latency=%.2fs",
        GROQ_MODEL, usage.prompt_tokens, usage.completion_tokens, latency,
    )

    return {
        "answer":            answer,
        "model":             GROQ_MODEL,
        "prompt_tokens":     usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "latency_s":         latency,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query(
    question: str,
    top_k: int = TOP_K,
    save: bool = True,
) -> dict:
    """
    Full RAG query: retrieve relevant chunks → generate answer via Groq.

    Parameters
    ----------
    question : natural-language question
    top_k    : number of chunks to retrieve
    save     : if True, append full result to RESULT_PATH

    Returns
    -------
    Complete result dict (question, answer, sources, metrics, timestamps)
    """
    log.info("Query received: '%s'", question)
    t_start = time.perf_counter()

    # 1. Retrieve
    top_chunks = retrieve(question, top_k=top_k)

    # 2. Generate
    gen = generate_answer(question, top_chunks)

    total_latency = round(time.perf_counter() - t_start, 3)

    result = {
        "query_id":    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "question":    question,
        "answer":      gen["answer"],
        "sources": [
            {
                "id":         c["id"],
                "source":     c["source"],
                "chunk_idx":  c["chunk_idx"],
                "similarity": c["similarity"],
                "snippet":    c["text"][:200] + ("…" if len(c["text"]) > 200 else ""),
            }
            for c in top_chunks
        ],
        "metrics": {
            "top_k":             top_k,
            "model":             gen["model"],
            "prompt_tokens":     gen["prompt_tokens"],
            "completion_tokens": gen["completion_tokens"],
            "llm_latency_s":     gen["latency_s"],
            "total_latency_s":   total_latency,
        },
    }

    if save:
        append_result(result)

    return result


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, textwrap

    parser = argparse.ArgumentParser(description="RAG Query – ask a question against the indexed documents")
    parser.add_argument("question", help="Natural-language question to answer")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Number of chunks to retrieve")
    parser.add_argument("--no-save", action="store_true", help="Don't append result to results file")
    args = parser.parse_args()

    result = query(args.question, top_k=args.top_k, save=not args.no_save)

    print("\n" + "═" * 70)
    print(f"❓ Question : {result['question']}")
    print("═" * 70)
    print(f"💬 Answer   :\n{textwrap.fill(result['answer'], width=70)}")
    print("─" * 70)
    print(f"📚 Sources  :")
    for s in result["sources"]:
        print(f"   [{s['similarity']:.4f}] {s['source']} (chunk {s['chunk_idx']})")
    print("─" * 70)
    m = result["metrics"]
    print(f"⚙  Metrics  : {m['top_k']} chunks | {m['model']} | "
          f"{m['prompt_tokens']}+{m['completion_tokens']} tokens | "
          f"{m['total_latency_s']}s total")
    print("═" * 70)
    print(f"\n✅  Full result saved → {RESULT_PATH}")
