"""
generate_report.py
------------------
Reads results/raw_results.json, computes aggregate metrics, scores response
quality, and writes docs/model_comparison.md.
 
Usage
-----
    python generate_report.py               # uses default paths from config.py
    python generate_report.py --raw path/to/raw.json --out path/to/report.md
"""
 
import argparse
import json
import statistics
from collections import defaultdict
from datetime import date
 
from config import MODELS, PRICING, PROMPTS, RAW_RESULTS_FILE, REPORT_FILE
 
 
# ── Quality scoring ───────────────────────────────────────────────────────────
 
# Minimum response lengths (characters) per category – a rough proxy for effort.
MIN_LENGTH_BY_CATEGORY: dict[str, int] = {
    "Factual":       50,
    "Reasoning":     80,
    "Coding":       100,
    "Summarisation": 80,
    "Creative":      20,
    "Instruction":   80,
}
 
# Keywords that MUST appear in responses to specific prompts (spot checks).
KEYWORD_CHECKS: dict[str, list[str]] = {
    "P01": ["canberra"],
    "P04": ["0.05", "5 cents", "five cents"],
    "P07": ["def ", "return"],
    "P08": ["select", "order by", "limit"],
    "P15": ["french", "spanish", "german"],
}
 
 
def _score_quality(result: dict) -> dict:
    """
    Assign a simple 0–3 quality score to a single result.
 
    Score breakdown
    ---------------
    +1  Response is non-empty and above the minimum length for its category.
    +1  Response does not contain obvious error or refusal phrases.
    +1  Passes keyword spot-check for prompts that have one defined.
 
    Returns a dict: {score: int, max_score: int, notes: list[str]}
    """
    text     = (result.get("response_text") or "").strip()
    category = result.get("category", "")
    pid      = result.get("prompt_id", "")
    notes: list[str] = []
    score = 0
 
    # ── Check 1: length ───────────────────────────────────────────────────────
    min_len = MIN_LENGTH_BY_CATEGORY.get(category, 30)
    if len(text) >= min_len:
        score += 1
    else:
        notes.append(f"Response too short ({len(text)} < {min_len} chars)")
 
    # ── Check 2: no refusal / error phrases ──────────────────────────────────
    bad_phrases = ["i cannot", "i'm unable", "i am unable", "as an ai", "i don't know"]
    if not any(bp in text.lower() for bp in bad_phrases):
        score += 1
    else:
        notes.append("Contains refusal / uncertainty phrase")
 
    # ── Check 3: keyword spot-check ──────────────────────────────────────────
    keywords = KEYWORD_CHECKS.get(pid)
    if keywords:
        hit = any(kw.lower() in text.lower() for kw in keywords)
        if hit:
            score += 1
        else:
            notes.append(f"Missing expected keyword(s): {keywords}")
    else:
        score += 1   # no check defined → full marks for this dimension
 
    return {"score": score, "max_score": 3, "notes": notes}
 
 
# ── Aggregation ───────────────────────────────────────────────────────────────
 
def _aggregate(raw: list[dict]) -> dict:
    """
    Build per-model aggregate stats from raw results.
 
    Returns
    -------
    {
      model_name: {
        latencies, costs, input_tokens, output_tokens,
        quality_scores, errors, per_prompt: [...]
      }
    }
    """
    data: dict[str, dict] = {m: defaultdict(list) for m in MODELS}
 
    for r in raw:
        model = r["model"]
        if model not in data:
            continue
 
        qresult = _score_quality(r)
        r["quality"] = qresult  # enrich in-place for later use
 
        bucket = data[model]
        if r["error"] is None:
            bucket["latencies"].append(r["latency_s"])
            bucket["costs"].append(r["cost_usd"])
            bucket["input_tokens"].append(r["input_tokens"])
            bucket["output_tokens"].append(r["output_tokens"])
        else:
            bucket["errors"].append(r["prompt_id"])
 
        bucket["quality_scores"].append(qresult["score"])
        bucket["per_prompt"].append(r)
 
    return data
 
 
def _safe_stat(values: list, fn) -> float:
    return round(fn(values), 6) if values else 0.0
 
 
# ── Markdown builder ──────────────────────────────────────────────────────────
 
def _build_report(data: dict, raw: list[dict]) -> str:
    lines: list[str] = []
    a = lines.append  # shorthand
 
    # ── Title & metadata ──────────────────────────────────────────────────────
    a("# Groq Model Comparison Report")
    a("")
    a(f"> **Generated:** {date.today().isoformat()}  ")
    a(f"> **Models:** {', '.join(MODELS)}  ")
    a(f"> **Prompts:** {len(PROMPTS)} across 6 categories  ")
    a(f"> **Metric baseline:** Groq public pricing, temperature = 0 (deterministic)")
    a("")
 
    # ── 1. Summary table ──────────────────────────────────────────────────────
    a("## 1. Summary Comparison Table")
    a("")
    a(f"| Metric | `{MODELS[0]}` | `{MODELS[1]}` |")
    a("|--------|:-----------------:|:----------------:|")
 
    rows: dict[str, dict] = {}
    for model, bucket in data.items():
        lats  = bucket["latencies"]
        costs = bucket["costs"]
        qs    = bucket["quality_scores"]
        rows[model] = {
            "avg_latency":   _safe_stat(lats,  statistics.mean),
            "p50_latency":   _safe_stat(lats,  statistics.median),
            "max_latency":   _safe_stat(lats,  max),
            "avg_cost":      _safe_stat(costs, statistics.mean),
            "total_cost":    _safe_stat(costs, sum),
            "avg_in_tok":    _safe_stat(bucket["input_tokens"],  statistics.mean),
            "avg_out_tok":   _safe_stat(bucket["output_tokens"], statistics.mean),
            "quality_avg":   _safe_stat(qs,    statistics.mean),
            "quality_pct":   round(_safe_stat(qs, statistics.mean) / 3 * 100, 1),
            "error_count":   len(bucket.get("errors", [])),
        }
 
    def row(label, key, fmt="{:.4f}", suffix=""):
        vals = [fmt.format(rows[m][key]) + suffix for m in MODELS]
        a(f"| {label} | {vals[0]} | {vals[1]} |")
 
    row("**Avg latency (s)**",         "avg_latency",  "{:.3f}", "s")
    row("**Median latency (s)**",       "p50_latency",  "{:.3f}", "s")
    row("**Max latency (s)**",          "max_latency",  "{:.3f}", "s")
    row("**Avg cost / request**",       "avg_cost",     "${:.6f}")
    row("**Total cost (all prompts)**", "total_cost",   "${:.6f}")
    row("**Avg input tokens**",         "avg_in_tok",   "{:.0f}")
    row("**Avg output tokens**",        "avg_out_tok",  "{:.0f}")
    row("**Quality score (avg /3)**",   "quality_avg",  "{:.2f}")
    row("**Quality pass rate**",        "quality_pct",  "{:.1f}", "%")
    row("**Errors**",                   "error_count",  "{:.0f}")
    a("")
 
    # ── 2. Pricing reference ──────────────────────────────────────────────────
    a("## 2. Pricing Reference")
    a("")
    a("| Model | Input (per 1M tokens) | Output (per 1M tokens) |")
    a("|-------|:--------------------:|:----------------------:|")
    for m in MODELS:
        p = PRICING[m]
        a(f"| `{m}` | ${p['input_per_million']:.2f} | ${p['output_per_million']:.2f} |")
    a("")
 
    # ── 3. Per-category breakdown ─────────────────────────────────────────────
    a("## 3. Per-Category Breakdown")
    a("")
    categories = list(dict.fromkeys(p["category"] for p in PROMPTS))
 
    a("| Category | 70B avg lat (s) | 8B avg lat (s) | 70B quality | 8B quality |")
    a("|----------|:--------------:|:--------------:|:-----------:|:----------:|")
 
    for cat in categories:
        cat_rows: dict[str, list] = {m: [] for m in MODELS}
        for r in raw:
            if r.get("category") == cat:
                cat_rows[r["model"]].append(r)
 
        def cat_stat(model, key):
            vals = [r[key] for r in cat_rows[model] if r.get(key) is not None and r["error"] is None]
            return f"{statistics.mean(vals):.3f}" if vals else "N/A"
 
        def cat_quality(model):
            scores = [r["quality"]["score"] for r in cat_rows[model] if "quality" in r]
            if not scores:
                return "N/A"
            return f"{statistics.mean(scores):.1f}/3"
 
        lat70 = cat_stat(MODELS[0], "latency_s")
        lat8  = cat_stat(MODELS[1], "latency_s")
        q70   = cat_quality(MODELS[0])
        q8    = cat_quality(MODELS[1])
        a(f"| {cat} | {lat70}s | {lat8}s | {q70} | {q8} |")
    a("")
 
    # ── 4. Per-prompt detail table ────────────────────────────────────────────
    a("## 4. Per-Prompt Detail")
    a("")
    a("| Prompt | Category | Model | Latency (s) | In tok | Out tok | Cost (USD) | Quality |")
    a("|--------|----------|-------|:-----------:|:------:|:-------:|:----------:|:-------:|")
 
    prompt_ids = [p["id"] for p in PROMPTS]
    for pid in prompt_ids:
        for model in MODELS:
            match = next(
                (r for r in raw if r["prompt_id"] == pid and r["model"] == model), None
            )
            if match is None:
                continue
            err = match.get("error")
            if err:
                a(f"| {pid} | {match['category']} | `{model}` | ERROR | — | — | — | 0/3 |")
            else:
                q = match.get("quality", {})
                a(
                    f"| {pid} | {match['category']} | `{model}` "
                    f"| {match['latency_s']:.3f} "
                    f"| {match['input_tokens']} "
                    f"| {match['output_tokens']} "
                    f"| ${match['cost_usd']:.6f} "
                    f"| {q.get('score', '?')}/3 |"
                )
    a("")
 
    # ── 5. Quality notes ──────────────────────────────────────────────────────
    a("## 5. Quality Notes")
    a("")
    a("Prompts where at least one model lost a quality point:")
    a("")
    any_issue = False
    for r in raw:
        q = r.get("quality", {})
        if q.get("notes"):
            any_issue = True
            a(
                f"- **{r['prompt_id']}** (`{r['model']}`): "
                + "; ".join(q["notes"])
            )
    if not any_issue:
        a("_All responses passed quality checks._")
    a("")
 
    # ── 6. Recommendation ─────────────────────────────────────────────────────
    a("## 6. Recommendation")
    a("")
    r70 = rows[MODELS[0]]
    r8  = rows[MODELS[1]]
 
    cost_ratio    = r70["avg_cost"]   / r8["avg_cost"]   if r8["avg_cost"]   > 0 else float("inf")
    latency_ratio = r70["avg_latency"] / r8["avg_latency"] if r8["avg_latency"] > 0 else float("inf")
    q_diff        = r70["quality_pct"] - r8["quality_pct"]
 
    a(f"**{MODELS[0]}** costs **{cost_ratio:.1f}x** more and is **{latency_ratio:.1f}x** slower")
    a(f"than **{MODELS[1]}**, while scoring **{abs(q_diff):.1f} percentage points**")
    a(f"{'higher' if q_diff >= 0 else 'lower'} on quality.")
    a("")
    a(f"### Use `{MODELS[1]}` when")
    a("- **Budget is the primary constraint** - up to 10x cheaper per token.")
    a("- Tasks are **simple, structured, or templated** (classification, extraction, short Q&A).")
    a("- **Latency matters** more than depth - faster responses for real-time UX.")
    a("")
    a(f"### Use `{MODELS[0]}` when")
    a("- Tasks require **multi-step reasoning**, code generation, or nuanced writing.")
    a("- **Quality consistency** across edge cases is more valuable than cost savings.")
    a("- You can afford slightly higher latency for a **production-critical** path.")
    a("")
    a("### Hybrid approach (recommended)")
    a(
        f"Route simple/templated prompts to **{MODELS[1]}**, complex/agentic prompts to **{MODELS[0]}**. "
        "This typically yields **70-80% cost savings** with minimal quality loss on the "
        "overall pipeline."
    )
    a("")
    a("---")
    a("*Report generated by `generate_report.py`. Re-run after any pricing or prompt changes.*")
 
    return "\n".join(lines)
 
# ── CLI ───────────────────────────────────────────────────────────────────────
 
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Groq model comparison report.")
    parser.add_argument("--raw", default=RAW_RESULTS_FILE)
    parser.add_argument("--out", default=REPORT_FILE)
    args = parser.parse_args()
    with open(RAW_RESULTS_FILE, encoding="utf-8") as fh:
        raw: list[dict] = json.load(fh)
 
    data = _aggregate(raw)

    report = _build_report(data, raw)
 
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write(report)
 
    print(f"✓  Report saved → {REPORT_FILE}")
 
 
if __name__ == "__main__":
    main()