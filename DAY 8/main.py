"""
main.py – Entry point
======================
Runs the full workflow against the test set, prints a live log,
and saves all results to test_results.json.

Usage:
    pip install google-generativeai
    export GEMINI_API_KEY=your_key_here
    python main.py

Output:
    - Live per-ticket log printed to stdout
    - Final summary: total / success / fail / rate
    - DB views printed: run_summary, category_breakdown
    - test_results.json written in the same directory
"""

import json
from datetime import datetime,UTC

from db import init_db, get_conn
from pipeline import process_ticket
from test_inputs import TEST_INPUTS


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _print_row(i: int, rec) -> None:
    fmt    = "{:<4} {:<12} {:<10} {:<7} {:<10} {}"
    step   = rec.error_step or "—"
    detail = rec.error_msg if rec.status == "failed" else (rec.summary or "—")
    tokens = rec.completion.total_token_count or 0
    print(fmt.format(
        i,
        (rec.category or "—")[:12],
        rec.status[:10],
        rec.latency_ms,
        tokens,
        detail[:55],
    ))


def _print_summary(records: list) -> None:
    total   = len(records)
    success = sum(1 for r in records if r.status == "success")
    failed  = total - success
    rate    = 100.0 * success / total if total else 0

    print("\n" + "=" * 75)
    print(f"  Total: {total}  |  Success: {success}  |  Failed: {failed}  |  Rate: {rate:.1f}%")
    print(f"  Target ≥ 90%: {'✓ PASS' if rate >= 90.0 else '✗ FAIL'}")
    print("=" * 75)

    if failed:
        print("\nFailed tickets:")
        for r in records:
            if r.status == "failed":
                print(f"  [{r.error_step}] {r.error_msg} — \"{r.raw_text[:60]}...\"")


def _print_db_report() -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM run_summary").fetchone()
        if row:
            print("\nDB run_summary:")
            for k in row.keys():
                print(f"  {k:<25} {row[k]}")

        cats = conn.execute("SELECT * FROM category_breakdown").fetchall()
        if cats:
            print("\nCategory breakdown:")
            print(f"  {'category':<14} {'count':>5}   {'pct':>6}")
            print("  " + "-" * 28)
            for c in cats:
                print(f"  {c['category']:<14} {c['count']:>5}   {c['pct']:>5}%")


# ---------------------------------------------------------------------------
# Save test_results.json
# ---------------------------------------------------------------------------

def _save_results(records: list, run_started: str) -> None:
    total   = len(records)
    success = sum(1 for r in records if r.status == "success")
    failed  = total - success
    rate    = round(100.0 * success / total, 1) if total else 0

    output = {
        "run_started_at": run_started,
        "run_completed_at":datetime.now(UTC).isoformat() ,
        "summary": {
            "total":        total,
            "successful":   success,
            "failed":       failed,
            "success_rate": f"{rate}%",
            "pass":         rate >= 90.0,
        },
        "results": [r.to_dict() for r in records],
    }

    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved to test_results.json ({total} records)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()
    run_started = datetime.now(UTC).isoformat()

    print(f"\n{'=' * 75}")
    print("  Multi-step AI Workflow – Test Run")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {len(TEST_INPUTS)} inputs")
    print(f"{'=' * 75}\n")

    fmt = "{:<4} {:<12} {:<10} {:<7} {:<10} {}"
    print(fmt.format("#", "Category", "Status", "ms", "Tokens", "Summary / Error"))
    print("-" * 75)

    records = []
    for i, text in enumerate(TEST_INPUTS, 1):
        print(f"  [{i:02d}/{len(TEST_INPUTS)}] processing...", end="\r")
        rec = process_ticket(text)
        records.append(rec)
        _print_row(i, rec)

    _print_summary(records)
    _print_db_report()
    _save_results(records, run_started)


if __name__ == "__main__":
    main()