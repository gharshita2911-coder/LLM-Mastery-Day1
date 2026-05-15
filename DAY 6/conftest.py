"""
conftest.py — pytest plugin
Automatically collects every test result and saves them to
test_results.json after the session ends. No manual step needed.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ── in-memory store written by the hook, saved at session end ──────────────
_RESULTS: list[dict] = []
_SESSION_START: float = 0.0


def pytest_sessionstart(session):
    global _SESSION_START
    _SESSION_START = time.monotonic()


def pytest_runtest_logreport(report):
    """
    Called three times per test (setup / call / teardown).
    We only care about the 'call' phase — that is the actual test body.
    """
    if report.when != "call":
        return

    # Map pytest outcome to our vocabulary
    outcome_map = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}
    outcome = outcome_map.get(report.outcome, report.outcome.upper())

    # Extract category from the node id  (e.g. TestInputLength → A: input length)
    cat_map = {
        "TestInputLength":   "A: Input Length Validation",
        "TestOutputSchema":  "B: Output Schema Validation",
        "TestRetryLogic":    "C: Retry Logic",
        "TestTimeoutHandling": "D: Timeout Handling",
        "TestEndToEndNoCrash": "E: End-to-End / No-Crash",
    }
    category = "Uncategorised"
    for key, label in cat_map.items():
        if key in report.nodeid:
            category = label
            break

    entry = {
        "id":       len(_RESULTS) + 1,
        "nodeid":   report.nodeid,
        "category": category,
        "outcome":  outcome,
        "duration": round(report.duration, 6),
        "error":    None,
    }

    if report.outcome == "failed":
        # Capture the short failure message without ANSI codes
        entry["error"] = str(report.longrepr).splitlines()[-1] if report.longrepr else "unknown"

    _RESULTS.append(entry)


def pytest_sessionfinish(session, exitstatus):
    """Called once after all tests finish — write the JSON file."""
    elapsed = round(time.monotonic() - _SESSION_START, 3)

    passed  = sum(1 for r in _RESULTS if r["outcome"] == "PASS")
    failed  = sum(1 for r in _RESULTS if r["outcome"] == "FAIL")
    skipped = sum(1 for r in _RESULTS if r["outcome"] == "SKIP")

    # Per-category breakdown
    categories: dict[str, dict] = {}
    for r in _RESULTS:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        categories[cat]["total"]  += 1
        if r["outcome"] == "PASS":
            categories[cat]["passed"]  += 1
        elif r["outcome"] == "FAIL":
            categories[cat]["failed"]  += 1
        else:
            categories[cat]["skipped"] += 1

    report = {
        "meta": {
            "title":      "Phase 2 — RAG Guardrail Test Suite",
            "generated":  datetime.now(timezone.utc).isoformat(),
            "total":      len(_RESULTS),
            "passed":     passed,
            "failed":     failed,
            "skipped":    skipped,
            "crashes":    0,
            "duration_s": elapsed,
            "exit_status": exitstatus,
        },
        "summary_by_category": categories,
        "test_cases": _RESULTS,
    }

    out = Path(__file__).parent / "test_results.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  ✓  Results saved → {out}")
