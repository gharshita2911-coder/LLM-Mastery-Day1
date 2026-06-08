"""
Cost Tracker — Per-Query & Aggregate Cost Logging
==================================================
Tracks token usage and computes USD cost per query using Groq pricing.
Logs to a rolling in-memory list and optionally to disk.
"""

import time
from typing import Optional

from config import MODEL_PRICING, DEFAULT_PRICING, RAG_MODEL


class CostTracker:
    """Tracks token usage and cost per RAG query."""

    def __init__(self) -> None:
        self._runs: list[dict] = []
        self._start_time: float = time.time()

    # ── Record a single model call ─────────────────────────────────────────────

    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        model: Optional[str] = None,
        elapsed_seconds: float = 0.0,
    ) -> dict:
        """
        Record token usage and compute cost for one model call.

        Returns a dict with usage and cost breakdown.
        """
        model = model or RAG_MODEL
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

        input_cost = (prompt_tokens / 1_000_000) * pricing["input_per_million"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output_per_million"]
        total_cost = round(input_cost + output_cost, 8)

        record: dict = {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "input_cost_usd": round(input_cost, 8),
            "output_cost_usd": round(output_cost, 8),
            "cost_usd": total_cost,
            "elapsed_seconds": round(elapsed_seconds, 4),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        self._runs.append(record)
        return record

    # ── Aggregate queries (a single RAG answer may involve multiple calls) ─────

    def record_query(
        self,
        query_id: str,
        calls: list[dict],
    ) -> dict:
        """
        Aggregate multiple model calls into a single query record.

        *calls* is a list of dicts returned by *record* above.
        Returns a summarised query record.
        """
        total_cost = sum(c.get("cost_usd", 0.0) for c in calls)
        total_prompt = sum(c.get("prompt_tokens", 0) for c in calls)
        total_completion = sum(c.get("completion_tokens", 0) for c in calls)
        total_tokens = total_prompt + total_completion
        total_latency = sum(c.get("elapsed_seconds", 0.0) for c in calls)

        query_record: dict = {
            "query_id": query_id,
            "num_calls": len(calls),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "cost_usd": round(total_cost, 8),
            "latency_seconds": round(total_latency, 4),
            "calls": calls,
        }
        return query_record

    # ── Summary ────────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return aggregate cost/usage summary across all recorded queries."""
        if not self._runs:
            return {
                "total_cost_usd": 0.0,
                "total_queries": 0,
                "total_tokens": 0,
            }

        total_cost = sum(r.get("cost_usd", 0.0) for r in self._runs)
        total_tokens = sum(r.get("total_tokens", 0) for r in self._runs)
        total_elapsed = sum(r.get("elapsed_seconds", 0.0) for r in self._runs)

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_runs": len(self._runs),
            "total_tokens": total_tokens,
            "total_latency_seconds": round(total_elapsed, 3),
            "uptime_seconds": round(time.time() - self._start_time, 1),
        }

    def clear(self) -> None:
        """Clear all recorded runs."""
        self._runs.clear()
        self._start_time = time.time()
