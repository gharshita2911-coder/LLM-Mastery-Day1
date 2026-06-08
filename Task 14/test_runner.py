"""
Test Runner — Phase 2 E2E Test Suite for RAG System
=====================================================
Runs all 20 test queries through the RAG engine, evaluates responses
with LLM-as-a-judge, tracks cost and latency, and writes results to
test_results.json + a human-readable summary.
"""

import json
import os
from datetime import datetime, timezone

from config import (
    LATENCY_TARGET_SECONDS,
    VALIDATION_TARGET_PCT,
    RELEVANCE_TARGET_PCT,
    FAITHFULNESS_TARGET_PCT,
)
from rag_engine import run_rag_query, reset_cost_tracker
from evaluator import grade_relevance, grade_faithfulness
from test_queries import TEST_QUERIES


# ── Paths ──────────────────────────────────────────────────────────────────────

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(OUT_DIR, "test_results.json")
SUMMARY_FILE = os.path.join(OUT_DIR, "phase2_test_summary.json")


# ── Terminal helpers ───────────────────────────────────────────────────────────

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _color(status: str, text: str) -> str:
    mapping = {
        "PASS": f"{_GREEN}{_BOLD}PASS{_RESET}",
        "FAIL": f"{_RED}{_BOLD}FAIL{_RESET}",
        "WARN": f"{_YELLOW}WARN{_RESET}",
        "INFO": f"{_CYAN}INFO{_RESET}",
    }
    prefix = mapping.get(status, status)
    return f"{prefix} {text}"


# ── Main test run ──────────────────────────────────────────────────────────────

def run_tests() -> None:
    """Run the full Phase 2 E2E test suite."""
    # Reset cost tracker for a clean run
    reset_cost_tracker()

    print()
    print("=" * 74)
    print(f"  {_BOLD}RAG Phase 2 — E2E Verification & Metrics Grading{_RESET}")
    print("=" * 74)
    print(f"  Queries : {len(TEST_QUERIES)}")
    print(f"  Model   : see config.py")
    print(f"  Targets : Latency < {LATENCY_TARGET_SECONDS}s | "
          f"Valid >= {VALIDATION_TARGET_PCT}% | "
          f"Relevance >= {RELEVANCE_TARGET_PCT}% | "
          f"Faithfulness >= {FAITHFULNESS_TARGET_PCT}%")
    print("=" * 74)
    print()

    all_results: list[dict] = []
    valid_count: int = 0
    invalid_count: int = 0
    fallback_count: int = 0
    confidence_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    # ── Run each query ────────────────────────────────────────────────────────
    for i, query in enumerate(TEST_QUERIES):
        qid = f"Q{i:02d}"
        print(f"  [{qid}] Processing...", end=" ", flush=True)

        # Execute RAG query
        result = run_rag_query(query)

        is_valid = result.get("valid", False)
        conf = result.get("confidence", "low")
        nsrc = len(result.get("sources", []))
        attempts = result.get("attempts", 0)
        elapsed = result.get("elapsed_seconds", 0.0)
        used_fb = result.get("used_fallback", False)

        # Run LLM-as-a-judge evaluations
        print(f"grading...", end=" ", flush=True)
        relevance_ok, relevance_exp, pt_rel, ct_rel = grade_relevance(
            query, result.get("chunks_retrieved", [])
        )
        faithfulness_ok, faithfulness_exp, pt_faith, ct_faith = grade_faithfulness(
            result.get("answer", ""), result.get("chunks_retrieved", [])
        )

        # Annotate result with evaluation data
        annotated = {
            "query_id": qid,
            "query": query,
            "answer": result.get("answer", ""),
            "confidence": conf,
            "sources": result.get("sources", []),
            "valid": is_valid,
            "client_valid": is_valid,
            "server_valid": result.get("server_valid", True),
            "attempts": attempts,
            "used_fallback": used_fb,
            "error": result.get("error", ""),
            "chunks_retrieved": result.get("chunks_retrieved", []),
            "elapsed_seconds": elapsed,
            "timestamp": result.get("timestamp", ""),
            "prompt_tokens": result.get("prompt_tokens", 0),
            "completion_tokens": result.get("completion_tokens", 0),
            "total_tokens": result.get("total_tokens", 0),
            "cost_usd": result.get("cost_usd", 0.0),
            "relevance_ok": relevance_ok,
            "relevance_explanation": relevance_exp,
            "faithfulness_ok": faithfulness_ok,
            "faithfulness_explanation": faithfulness_exp,
        }

        # ── Print per-query summary ──────────────────────────────────────────
        short_q = query[:65] + ("…" if len(query) > 65 else "")
        print()
        print(f"       Query    : {short_q}")

        if is_valid:
            valid_count += 1
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1
            fb_flag = " [FALLBACK]" if used_fb else ""
            print(
                f"       Status   : {_color('PASS', f'VALID{fb_flag}')} | "
                f"confidence={conf} | sources={nsrc} | "
                f"attempts={attempts} | {elapsed}s"
            )
            if used_fb:
                fallback_count += 1
        else:
            invalid_count += 1
            print(
                f"       Status   : {_color('FAIL', 'INVALID')} | "
                f"attempts={attempts} | {elapsed}s"
            )
            print(f"         Error  : {result.get('error', '')}")

        rel_status = _color("PASS", "✓") if relevance_ok else _color("FAIL", "✗")
        faith_status = _color("PASS", "✓") if faithfulness_ok else _color("FAIL", "✗")
        print(f"       Relevance: {rel_status} — {relevance_exp}")
        print(f"       Faithful : {faith_status} (No Hallucination) — {faithfulness_exp}")
        print()

        all_results.append(annotated)

    # ── Calculate metrics ─────────────────────────────────────────────────────
    total_queries = len(TEST_QUERIES)
    valid_pct = round((valid_count / total_queries) * 100, 1)
    target_met = valid_pct >= VALIDATION_TARGET_PCT

    total_cost = sum(r["cost_usd"] for r in all_results)
    total_latency = sum(r["elapsed_seconds"] for r in all_results)
    avg_latency = round(total_latency / total_queries, 3)

    relevance_count = sum(1 for r in all_results if r["relevance_ok"])
    relevance_pct = round((relevance_count / total_queries) * 100, 1)

    faithful_count = sum(1 for r in all_results if r["faithfulness_ok"])
    faithful_pct = round((faithful_count / total_queries) * 100, 1)

    avg_prompt_tokens = round(sum(r["prompt_tokens"] for r in all_results) / total_queries, 1)
    avg_completion_tokens = round(sum(r["completion_tokens"] for r in all_results) / total_queries, 1)
    avg_total_tokens = round(sum(r["total_tokens"] for r in all_results) / total_queries, 1)

    # ── Build summary ─────────────────────────────────────────────────────────
    validation_failures = [
        {
            "query_id": r["query_id"],
            "query": r["query"],
            "error": r["error"],
            "attempts": r["attempts"],
        }
        for r in all_results
        if not r["valid"]
    ]

    summary = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": total_queries,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "valid_percentage": valid_pct,
        f"target_{int(VALIDATION_TARGET_PCT)}_pct_met": target_met,
        "fallback_used_count": fallback_count,
        "avg_attempts_per_query": round(
            sum(r["attempts"] for r in all_results) / total_queries, 2
        ),
        "confidence_distribution": confidence_dist,
        "validation_failures": validation_failures,
        "performance_and_cost": {
            "total_cost_usd": round(total_cost, 6),
            "avg_cost_per_query_usd": round(total_cost / total_queries, 8),
            "total_latency_seconds": round(total_latency, 3),
            "avg_latency_seconds": avg_latency,
            "avg_prompt_tokens": avg_prompt_tokens,
            "avg_completion_tokens": avg_completion_tokens,
            "avg_total_tokens": avg_total_tokens,
            "latency_target_met": avg_latency < LATENCY_TARGET_SECONDS,
        },
        "evaluation_metrics": {
            "retrieval_relevance_count": relevance_count,
            "retrieval_relevance_pct": relevance_pct,
            f"retrieval_relevance_met_{int(RELEVANCE_TARGET_PCT)}pct": relevance_pct >= RELEVANCE_TARGET_PCT,
            "faithfulness_no_hallucination_count": faithful_count,
            "faithfulness_no_hallucination_pct": faithful_pct,
            f"faithfulness_target_met_{int(FAITHFULNESS_TARGET_PCT)}pct": faithful_pct >= FAITHFULNESS_TARGET_PCT,
        },
        "schema_definition": {
            "answer": "str — non-empty answer string",
            "confidence": "'high' | 'medium' | 'low'",
            "sources": "list[dict] — each with chunkId, snippet, category",
        },
    }

    # ── Write results files ───────────────────────────────────────────────────
    with open(RESULTS_FILE, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"  {_color('INFO', f'Results written to {RESULTS_FILE}')}")

    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  {_color('INFO', f'Summary written to {SUMMARY_FILE}')}")

    # ── Print summary table ───────────────────────────────────────────────────
    print()
    print("=" * 74)
    print(f"  {_BOLD}FINAL RESULTS & METRICS SUMMARY{_RESET}")
    print("=" * 74)

    def _pass_fail(cond: bool) -> str:
        return _color("PASS", "✓") if cond else _color("FAIL", "✗")

    print(f"  Schema Valid Responses    : {valid_count}/{total_queries}  ({valid_pct}%)")
    print(f"  Target >=95% Valid Met    : {_pass_fail(target_met)}")
    print(f"  Average Latency           : {avg_latency}s  "
          f"(Target: < {LATENCY_TARGET_SECONDS}s)  "
          f"{_pass_fail(avg_latency < LATENCY_TARGET_SECONDS)}")
    print(f"  Total Cost                : ${total_cost:.6f} USD")
    print(f"  Avg Tokens per Query      : P: {avg_prompt_tokens} | "
          f"C: {avg_completion_tokens} | T: {avg_total_tokens}")
    print(f"  Fallbacks Used            : {fallback_count}/{total_queries}")
    print(f"  Retrieval Relevance       : {relevance_count}/{total_queries}  "
          f"({relevance_pct}%)  (Target: >= {RELEVANCE_TARGET_PCT}%)  "
          f"{_pass_fail(relevance_pct >= RELEVANCE_TARGET_PCT)}")
    print(f"  Faithfulness (No Halluc)  : {faithful_count}/{total_queries}  "
          f"({faithful_pct}%)  (Target: >= {FAITHFULNESS_TARGET_PCT}%)  "
          f"{_pass_fail(faithful_pct >= FAITHFULNESS_TARGET_PCT)}")
    print(f"  Confidence — high         : {confidence_dist.get('high', 0)}")
    print(f"  Confidence — medium       : {confidence_dist.get('medium', 0)}")
    print(f"  Confidence — low          : {confidence_dist.get('low', 0)}")

    if validation_failures:
        print(f"\n  {_color('WARN', f'Validation Failures ({len(validation_failures)}):')}")
        for vf in validation_failures:
            print(f"    - {vf['query_id']}: {vf['error']}")

    print()
    print("=" * 74)
    print(f"  {_BOLD}PHASE 2 E2E TEST RUN COMPLETE{_RESET}")
    print("=" * 74)
    print()


if __name__ == "__main__":
    run_tests()
