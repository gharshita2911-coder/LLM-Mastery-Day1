"""
retriever.py
------------
TF-IDF retriever over the knowledge base. Pure stdlib, no external deps.

Usage:
    from retriever import retrieve
    chunks = retrieve("What is Python?", top_k=3)
    # → [{ chunkId, doc, text, score }, ...]
"""

import math
import re
from collections import Counter
from knowledge_base import get_all_chunks

_CHUNKS = get_all_chunks()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z]{2,}\b", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    c = Counter(tokens)
    total = len(tokens) or 1
    return {w: n / total for w, n in c.items()}


def _build_idf(chunks: list[dict]) -> dict[str, float]:
    N  = len(chunks)
    df: dict[str, int] = {}
    for chunk in chunks:
        for w in set(_tokenize(chunk["text"])):
            df[w] = df.get(w, 0) + 1
    return {w: math.log((N + 1) / (f + 1)) + 1 for w, f in df.items()}


_IDF = _build_idf(_CHUNKS)


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Return top_k chunks ranked by TF-IDF similarity to query."""
    q_tokens = _tokenize(query)
    q_tf     = _tf(q_tokens)

    scored = []
    for chunk in _CHUNKS:
        c_tf  = _tf(_tokenize(chunk["text"]))
        score = sum(
            q_tf.get(w, 0) * c_tf.get(w, 0) * _IDF.get(w, 1.0)
            for w in set(q_tokens) | set(c_tf)
        )
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**ch, "score": round(s, 5)} for s, ch in scored[:top_k]]
