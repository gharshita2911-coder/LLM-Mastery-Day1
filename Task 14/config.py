"""
RAG Phase 2 — Configuration
============================
Centralised constants for model selection, latency targets, cost tracking,
and evaluation thresholds.
"""

import os

# ── Groq API ──────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY environment variable is not set. "
        "Please export GROQ_API_KEY=your_key_here"
    )

# Primary model for RAG generation (must support structured JSON output)
RAG_MODEL: str = "llama-3.1-8b-instant"

# Judge model used for LLM-as-a-judge evaluations (more capable)
JUDGE_MODEL: str = "llama-3.3-70b-versatile"

# Fallback model if primary fails
FALLBACK_MODEL: str = "llama3-8b-8192"

# ── RAG retrieval ─────────────────────────────────────────────────────────────
TOP_K: int = 3               # Number of chunks to retrieve per query
MAX_RETRIEVAL_ATTEMPTS: int = 3   # Max LLM attempts before fallback

# ── Performance targets (Phase 2) ─────────────────────────────────────────────
LATENCY_TARGET_SECONDS: float = 3.0        # Average latency target (< 3s)
VALIDATION_TARGET_PCT: float = 95.0        # >= 95% valid responses
RELEVANCE_TARGET_PCT: float = 90.0         # >= 90% retrieval relevance
FAITHFULNESS_TARGET_PCT: float = 95.0      # >= 95% no hallucination

# ── Cost model (Groq pricing per 1M tokens, USD) ──────────────────────────────
# Prices as of June 2026 – llama-3.1-8b-instant
MODEL_PRICING: dict[str, dict[str, float]] = {
    "llama-3.1-8b-instant": {
        "input_per_million": 0.05,
        "output_per_million": 0.08,
    },
    "llama3-8b-8192": {
        "input_per_million": 0.05,
        "output_per_million": 0.08,
    },
    "llama-3.3-70b-versatile": {
        "input_per_million": 0.59,
        "output_per_million": 0.79,
    },
}

DEFAULT_PRICING: dict[str, float] = {
    "input_per_million": 0.05,
    "output_per_million": 0.08,
}
