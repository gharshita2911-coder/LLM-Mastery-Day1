"""
test_runner.py
--------------
Phase 2 acceptance test:
  - Sends 20 RAG queries to POST /rag/batch on the running FastAPI server
  - Validates every response has answer + confidence + sources
  - Counts valid vs invalid; target ≥ 95%
  - Documents any validation failures
  - Saves full results to rag_test_results.json
  - Saves metrics summary to rag_test_summary.json

Usage:
  # Step 1 – start the server (in a separate terminal):
  #   export GROQ_API_KEY=gsk_...
  #   uvicorn app:app --port 8000

  # Step 2 – run the tests:
  python3 test_runner.py
  python3 test_runner.py --host http://localhost:8000   # custom host
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── 20 test queries (4 per topic area) ────────────────────────────────────────
TEST_QUERIES = [
    # Python
    "What is Python and what programming paradigms does it support?",
    "How does Python define code blocks differently from other languages?",
    "What modules are included in the Python standard library?",
    "Which Python libraries are used for machine learning and data analysis?",
    # Machine Learning
    "What is machine learning and how does it differ from explicit programming?",
    "What is the difference between supervised and unsupervised learning?",
    "How does backpropagation adjust weights in a neural network?",
    "What are CNNs and RNNs and what are they used for?",
    # RAG & LLMs
    "What is Retrieval-Augmented Generation and how does it work?",
    "How does RAG help reduce hallucinations in language model responses?",
    "What is a vector database and how does similarity search work?",
    "Name some popular vector databases used in production systems.",
    # Software Engineering
    "What are the SOLID principles in object-oriented software engineering?",
    "What is Test-Driven Development and what are its benefits?",
    "What HTTP methods does REST use and what does each one do?",
    "How is API versioning and authentication typically handled?",
    # Cloud & DevOps
    "What are the three cloud service models IaaS PaaS and SaaS?",
    "Which companies are the major cloud providers and what services do they offer?",
    "What is CI/CD and which tools are commonly used to implement it?",
    "How do Docker and Kubernetes work together in a production system?",
]
assert len(TEST_QUERIES) == 20, "Must be exactly 20 queries"

DEFAULT_HOST = "http://localhost:8000"
OUT_DIR      = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(OUT_DIR, "rag_test_results.json")
SUMMARY_FILE = os.path.join(OUT_DIR, "rag_test_summary.json")


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _post(url: str, payload: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"\n[HTTP ERROR {exc.code}] {url}\n{body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(
            f"\n[CONNECTION ERROR] Cannot reach {url}\n"
            f"  reason: {exc.reason}\n\n"
            f"  Make sure the server is running:\n"
            f"    export GROQ_API_KEY=gsk_...\n"
            f"    uvicorn app:app --port 8000\n",
            file=sys.stderr,
        )
        sys.exit(1)


def _check_health(host: str) -> None:
    url = f"{host}/health"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if not data.get("groq_key_set"):
            print(
                f"\n[WARNING] Server is running but GROQ_API_KEY is not set on the server.\n"
                f"  Set it before starting uvicorn:  export GROQ_API_KEY=gsk_...\n",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"  Server  : {host}")
        print(f"  Model   : {data.get('model')}")
        print(f"  Status  : {data.get('status')}")
    except Exception as exc:
        print(
            f"\n[ERROR] Health check failed: {exc}\n"
            f"  Is the server running?  uvicorn app:app --port 8000\n",
            file=sys.stderr,
        )
        sys.exit(1)


# ── Validate a single result dict against the schema ──────────────────────────

def _validate_result(r: dict) -> tuple[bool, str]:
    """
    Client-side schema re-validation so the test runner independently
    confirms every field — not just trusting the server's 'valid' flag.
    """
    resp = r.get("response") or r  # batch returns flat, single returns nested

    # answer
    answer = resp.get("answer", "")
    if not isinstance(answer, str) or not answer.strip():
        return False, "answer is missing or empty"

    # confidence
    conf = resp.get("confidence", "")
    if conf not in ("high", "medium", "low"):
        return False, f"confidence '{conf}' is not high/medium/low"

    # sources
    sources = resp.get("sources", [])
    if not isinstance(sources, list) or len(sources) == 0:
        return False, "sources is missing or empty"
    for i, src in enumerate(sources):
        if not src.get("chunkId"):
            return False, f"sources[{i}].chunkId is missing"
        if not src.get("snippet"):
            return False, f"sources[{i}].snippet is missing"

    return True, ""


# ── Main test run ──────────────────────────────────────────────────────────────

def run_tests(host: str) -> None:
    print("=" * 68)
    print("  RAG Phase 2 — Structured Output Validation Test Run")
    print("=" * 68)
    _check_health(host)
    print(f"  Queries : {len(TEST_QUERIES)}")
    print(f"  Target  : ≥ 95% valid structured output")
    print("=" * 68)

    # ── Send all 20 queries in one batch request ───────────────────────────────
    print("\n  Sending 20 queries to POST /rag/batch ...")
    batch_resp = _post(
        f"{host}/rag/batch",
        {"queries": TEST_QUERIES, "top_k": 3},
    )

    server_results = batch_resp["results"]
    assert len(server_results) == 20, f"Expected 20 results, got {len(server_results)}"

    # ── Per-query report ───────────────────────────────────────────────────────
    print()
    all_results     = []
    valid_count     = 0
    invalid_count   = 0
    fallback_count  = 0
    confidence_dist = {"high": 0, "medium": 0, "low": 0}

    for i, (query, result) in enumerate(zip(TEST_QUERIES, server_results), 1):
        # Client-side independent re-validation
        client_valid, client_err = _validate_result(result)

        # A result is only valid if both the server AND client agree
        is_valid = result.get("valid", False) and client_valid
        error    = result.get("error") or (client_err if not client_valid else None)

        annotated = {
            "query_id":        f"Q{i:02d}",
            "query":           query,
            "answer":          result.get("answer", ""),
            "confidence":      result.get("confidence", ""),
            "sources":         result.get("sources", []),
            "valid":           is_valid,
            "client_valid":    client_valid,
            "server_valid":    result.get("valid", False),
            "attempts":        result.get("attempts", 0),
            "used_fallback":   result.get("used_fallback", False),
            "error":           error,
            "chunks_retrieved": result.get("chunks_retrieved", []),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "timestamp":       result.get("timestamp", ""),
        }

        short = query[:60] + ("…" if len(query) > 60 else "")
        print(f"[Q{i:02d}] {short}")

        if is_valid:
            valid_count += 1
            conf = result.get("confidence", "?")
            nsrc = len(result.get("sources", []))
            fb   = " [FALLBACK]" if result.get("used_fallback") else ""
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1
            print(
                f"       ✓ VALID{fb}  confidence={conf}  "
                f"sources={nsrc}  attempts={result.get('attempts')}  "
                f"{result.get('elapsed_seconds')}s"
            )
            # Print first source to confirm it references a real chunk
            if result.get("sources"):
                src = result["sources"][0]
                print(f"       └─ source: [{src['chunkId']}] {src['snippet'][:70]}…")
        else:
            invalid_count += 1
            print(
                f"       ✗ INVALID  attempts={result.get('attempts')}  "
                f"{result.get('elapsed_seconds')}s"
            )
            print(f"         error: {error}")

        if result.get("used_fallback"):
            fallback_count += 1

        all_results.append(annotated)

    # ── Metrics ────────────────────────────────────────────────────────────────
    valid_pct  = round((valid_count / 20) * 100, 1)
    target_met = valid_pct >= 95.0

    validation_failures = [
        {
            "query_id":      r["query_id"],
            "query":         r["query"],
            "error":         r["error"],
            "attempts":      r["attempts"],
            "used_fallback": r["used_fallback"],
            "server_valid":  r["server_valid"],
            "client_valid":  r["client_valid"],
        }
        for r in all_results if not r["valid"]
    ]

    summary = {
        "run_timestamp":           datetime.now(timezone.utc).isoformat(),
        "endpoint":                f"{host}/rag/batch",
        "model":                   batch_resp.get("results", [{}])[0].get("model", "llama3-8b-8192"),
        "total_queries":           20,
        "valid_count":             valid_count,
        "invalid_count":           invalid_count,
        "valid_percentage":        valid_pct,
        "target_95_pct_met":       target_met,
        "fallback_used_count":     fallback_count,
        "avg_attempts_per_query":  round(
            sum(r["attempts"] for r in all_results) / 20, 2
        ),
        "confidence_distribution": confidence_dist,
        "validation_failures":     validation_failures,
        "schema_definition": {
            "answer":     "str — non-empty answer string",
            "confidence": "'high' | 'medium' | 'low'",
            "sources":    "list[{chunkId: str, snippet: str}] — min 1 item",
        },
    }

    # ── Print summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("  FINAL RESULTS")
    print("=" * 68)
    print(f"  Valid responses     : {valid_count}/20  ({valid_pct}%)")
    print(f"  Invalid responses   : {invalid_count}/20")
    print(f"  Fallbacks used      : {fallback_count}")
    print(f"  95% target met      : {'YES ✓' if target_met else 'NO  ✗'}")
    print(f"  Avg LLM attempts    : {summary['avg_attempts_per_query']}")
    print(f"  Confidence — high   : {confidence_dist['high']}")
    print(f"  Confidence — medium : {confidence_dist['medium']}")
    print(f"  Confidence — low    : {confidence_dist['low']}")

    if validation_failures:
        print(f"\n  Validation Failures ({len(validation_failures)}):")
        for f in validation_failures:
            print(f"    [{f['query_id']}] {f['query'][:55]}…")
            print(f"           error    : {f['error']}")
            print(f"           fallback : {f['used_fallback']}")
    else:
        print("\n  No validation failures — all 20 responses passed schema validation.")
    print("=" * 68)

    # ── Save JSON output ───────────────────────────────────────────────────────
    with open(RESULTS_FILE, "w") as fh:
        json.dump({"summary": summary, "results": all_results}, fh, indent=2)
    with open(SUMMARY_FILE, "w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\n  Saved: {RESULTS_FILE}")
    print(f"  Saved: {SUMMARY_FILE}\n")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Phase 2 test runner")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Base URL of the FastAPI server (default: {DEFAULT_HOST})",
    )
    args = parser.parse_args()
    run_tests(args.host)
