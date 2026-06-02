"""
Automated RAG Batch Runner
==========================
Reads stored queries from data/stored_queries.json
Executes each enabled query through the RAG pipeline
Saves all results to data/batch_results.json

Usage:
  python batch_runner.py                    # run all enabled queries
  python batch_runner.py --tags policy      # run only queries with tag 'policy'
  python batch_runner.py --id q001 q003     # run specific query IDs
  python batch_runner.py --dry-run          # list what would run, don't execute

Env vars:
  GROQ_API_KEY        (required)
  STORED_QUERIES_PATH (default: data/stored_queries.json)
  BATCH_RESULTS_PATH  (default: data/batch_results.json)
  DELAY_BETWEEN_S     (default: 1.0 — seconds between calls, avoids rate limits)
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── make sure src/ is importable ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from query import query as rag_query

# ── logging ───────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/batch_runner.log"),
    ],
)
log = logging.getLogger("rag.batch")

# ── config ────────────────────────────────────────────────────────────
STORED_QUERIES_PATH = Path(os.getenv("STORED_QUERIES_PATH", "data/stored_queries.json"))
BATCH_RESULTS_PATH  = Path(os.getenv("BATCH_RESULTS_PATH",  "data/batch_results.json"))
DELAY_BETWEEN_S     = float(os.getenv("DELAY_BETWEEN_S", "1.0"))


# ── helpers ───────────────────────────────────────────────────────────

def load_stored_queries() -> list[dict]:
    if not STORED_QUERIES_PATH.exists():
        raise FileNotFoundError(f"Stored queries file not found: {STORED_QUERIES_PATH}")
    with STORED_QUERIES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_batch_results(run: dict) -> None:
    BATCH_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if BATCH_RESULTS_PATH.exists():
        with BATCH_RESULTS_PATH.open("r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []
    history.append(run)
    with BATCH_RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    log.info("Batch run saved → %s (total runs stored: %d)", BATCH_RESULTS_PATH, len(history))


def filter_queries(
    all_queries: list[dict],
    ids: list[str] | None = None,
    tags: list[str] | None = None,
    enabled_only: bool = True,
) -> list[dict]:
    filtered = all_queries
    if enabled_only:
        filtered = [q for q in filtered if q.get("enabled", True)]
    if ids:
        filtered = [q for q in filtered if q.get("id") in ids]
    if tags:
        filtered = [q for q in filtered if any(t in q.get("tags", []) for t in tags)]
    return filtered


# ── core runner ───────────────────────────────────────────────────────

def run_batch(
    ids: list[str] | None = None,
    tags: list[str] | None = None,
    dry_run: bool = False,
    include_disabled: bool = False,
) -> dict:
    """
    Execute all matching stored queries and save a consolidated run report.

    Returns the full run dict (summary + per-query results).
    """
    all_queries = load_stored_queries()
    to_run = filter_queries(
        all_queries,
        ids=ids,
        tags=tags,
        enabled_only=not include_disabled,
    )

    run_id    = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_start = datetime.now(timezone.utc).isoformat()

    log.info("Batch run %s | %d queries selected (dry_run=%s)", run_id, len(to_run), dry_run)

    if dry_run:
        print(f"\n🔍 DRY RUN — {len(to_run)} queries would execute:\n")
        for q in to_run:
            print(f"  [{q['id']}] (top_k={q.get('top_k', 5)}) {q['question']}")
        print()
        return {"run_id": run_id, "dry_run": True, "queries": to_run}

    results   = []
    succeeded = 0
    failed    = 0

    for i, stored_q in enumerate(to_run, start=1):
        qid      = stored_q.get("id", f"auto_{i}")
        question = stored_q["question"]
        top_k    = stored_q.get("top_k", 5)

        log.info("[%d/%d] Running query %s: %s", i, len(to_run), qid, question)
        print(f"\n[{i}/{len(to_run)}] {qid}: {question}")

        try:
            result = rag_query(question, top_k=top_k, save=True)
            result["stored_query_id"] = qid
            result["stored_tags"]     = stored_q.get("tags", [])
            results.append({"status": "ok", "stored_query_id": qid, "result": result})
            succeeded += 1
            print(f"   ✅ Answer: {result['answer'][:120]}{'…' if len(result['answer']) > 120 else ''}")
            print(f"   ⚙  {result['metrics']['total_latency_s']}s | "
                  f"{result['metrics']['prompt_tokens']}+{result['metrics']['completion_tokens']} tokens")

        except Exception as exc:
            log.error("Query %s failed: %s", qid, exc, exc_info=True)
            results.append({"status": "error", "stored_query_id": qid, "error": str(exc)})
            failed += 1
            print(f"   ❌ Error: {exc}")

        if i < len(to_run):
            time.sleep(DELAY_BETWEEN_S)

    run_end = datetime.now(timezone.utc).isoformat()

    run_report = {
        "run_id":     run_id,
        "run_start":  run_start,
        "run_end":    run_end,
        "summary": {
            "total":     len(to_run),
            "succeeded": succeeded,
            "failed":    failed,
        },
        "filters": {"ids": ids, "tags": tags},
        "results":  results,
    }

    save_batch_results(run_report)

    print(f"\n{'═'*60}")
    print(f"✅ Batch run {run_id} complete")
    print(f"   Total: {len(to_run)} | ✅ {succeeded} | ❌ {failed}")
    print(f"   Results → {BATCH_RESULTS_PATH}")
    print(f"{'═'*60}\n")

    return run_report


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automated RAG batch runner — executes stored queries and saves results"
    )
    parser.add_argument("--id",       nargs="+", metavar="ID",  help="Run only specific query IDs (e.g. q001 q003)")
    parser.add_argument("--tags",     nargs="+", metavar="TAG", help="Run only queries matching these tags")
    parser.add_argument("--dry-run",  action="store_true",      help="List queries that would run, don't execute")
    parser.add_argument("--all",      action="store_true",      help="Include disabled queries too")
    args = parser.parse_args()

    run_batch(
        ids=args.id,
        tags=args.tags,
        dry_run=args.dry_run,
        include_disabled=args.all,
    )
