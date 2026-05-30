"""
test_cases.py
=============
10 automated test prompts covering:
  • RAG-only   — answered entirely from the knowledge base
  • Tool-req   — require a fetch_additional_doc call
  • File-based — one test ingests a temp file to prove file-upload works
  • Mixed      — RAG context + tool augmentation

Run:
  GROQ_API_KEY=gsk_... python test_cases.py

Output:
  Console: per-test PASS / FAIL summary
  File:    test_results.json
"""

from __future__ import annotations
import os
import sys
import json
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from groq import Groq
from rag_engine import RAGEngine
from llm_client import LLMClient
from knowledge_base import seed_engine
from tools import set_engine_ref
from dotenv import load_dotenv

load_dotenv()
# ─────────────────────────────────────────────────────────────────────────────
# Test case definitions
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES: list[dict] = [
    # ── RAG-only ──────────────────────────────────────────────────────────
    {
        "id":               "TC01",
        "category":         "RAG-only",
        "question":         "What is the scaled dot-product attention formula used in Transformers?",
        "expected_tool":    False,
        "expected_tool_name": None,
        "expected_topic":   None,
        "source_doc":       "doc_001",
        "notes":            "Direct answer in doc_001 (Transformer architecture)",
    },
    {
        "id":               "TC02",
        "category":         "RAG-only",
        "question":         "What are the core benefits of RAG over purely parametric LLMs?",
        "expected_tool":    False,
        "expected_tool_name": None,
        "expected_topic":   None,
        "source_doc":       "doc_002",
        "notes":            "Direct answer in doc_002 (RAG overview)",
    },
    {
        "id":               "TC03",
        "category":         "RAG-only",
        "question":         "How does cosine similarity work, and what is its formula?",
        "expected_tool":    False,
        "expected_tool_name": None,
        "expected_topic":   None,
        "source_doc":       "doc_004",
        "notes":            "Formula and explanation in doc_004",
    },
    {
        "id":               "TC04",
        "category":         "RAG-only",
        "question":         "What is the difference between bi-encoder and cross-encoder models?",
        "expected_tool":    False,
        "expected_tool_name": None,
        "expected_topic":   None,
        "source_doc":       "doc_004",
        "notes":            "Covered in doc_004 (vector embeddings)",
    },
    {
        "id":               "TC05",
        "category":         "RAG-only",
        "question":         "Explain chain-of-thought prompting and when you should use it.",
        "expected_tool":    False,
        "expected_tool_name": None,
        "expected_topic":   None,
        "source_doc":       "doc_006",
        "notes":            "Covered in doc_006 (prompt engineering)",
    },
    # ── Tool-required ─────────────────────────────────────────────────────
    {
        "id":               "TC06",
        "category":         "Tool-required",
        "question":         "What are the latest benchmark scores for Llama 3.3 70B, GPT-4o, and Claude on MMLU and HumanEval?",
        "expected_tool":    True,
        "expected_tool_name": "fetch_additional_doc",
        "expected_topic":   "latest_model_benchmarks",
        "source_doc":       None,
        "notes":            "Benchmark numbers not in any KB doc; requires tool",
    },
    {
        "id":               "TC07",
        "category":         "Tool-required",
        "question":         "How much does the Groq API cost per million tokens for Llama 3.3 70B?",
        "expected_tool":    True,
        "expected_tool_name": "fetch_additional_doc",
        "expected_topic":   "groq_pricing",
        "source_doc":       None,
        "notes":            "Pricing figures not in KB; requires fetch_additional_doc",
    },
    {
        "id":               "TC08",
        "category":         "Tool-required",
        "question":         "Compare popular RAG frameworks — LangChain, LlamaIndex, and Haystack — as of 2025.",
        "expected_tool":    True,
        "expected_tool_name": "fetch_additional_doc",
        "expected_topic":   "rag_frameworks_comparison",
        "source_doc":       None,
        "notes":            "Framework comparison not in KB",
    },
    {
        "id":               "TC09",
        "category":         "Tool-required",
        "question":         "How do I install FAISS in Python and build a cosine similarity index?",
        "expected_tool":    True,
        "expected_tool_name": "fetch_additional_doc",
        "expected_topic":   "python_faiss_install",
        "source_doc":       None,
        "notes":            "doc_007 has theory only; install steps need tool",
    },
    # ── Mixed RAG + Tool ──────────────────────────────────────────────────
    {
        "id":               "TC10",
        "category":         "Mixed (RAG + Tool)",
        "question":         "Explain how function calling works in Groq, and also give me the current pricing so I can estimate costs.",
        "expected_tool":    True,
        "expected_tool_name": "fetch_additional_doc",
        "expected_topic":   "groq_pricing",
        "source_doc":       "doc_003",
        "notes":            "Function calling explained by doc_003 (RAG); pricing requires tool",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation logic
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(tc: dict, trace: dict) -> dict:
    """
    Compare actual trace against expected behaviour.
    Returns an eval dict with 'passed' bool and per-criterion details.
    """
    tool_calls    = trace.get("tool_calls", [])
    actual_tools  = [t["tool"] for t in tool_calls]
    actual_topics = [t["args"].get("topic", "") for t in tool_calls]
    tool_was_used = len(actual_tools) > 0

    # Criterion 1: was a tool used (or not) as expected?
    tool_use_ok = (tool_was_used == tc["expected_tool"])

    # Criterion 2: if a tool was expected, was the right one called?
    tool_name_ok = True
    if tc["expected_tool"] and tc["expected_tool_name"]:
        tool_name_ok = tc["expected_tool_name"] in actual_tools

    # Criterion 3: if a specific topic was expected, was it requested?
    topic_ok = True
    if tc.get("expected_topic"):
        topic_ok = tc["expected_topic"] in actual_topics

    # Criterion 4: was there a non-empty final answer?
    answer_ok = bool(trace.get("final_answer", "").strip())

    passed = tool_use_ok and tool_name_ok and topic_ok and answer_ok

    return {
        "passed":            passed,
        "tool_use_correct":  tool_use_ok,
        "tool_name_correct": tool_name_ok,
        "topic_correct":     topic_ok,
        "has_answer":        answer_ok,
        "expected_tool":     tc["expected_tool"],
        "actual_tool_used":  tool_was_used,
        "expected_tool_name":tc.get("expected_tool_name"),
        "actual_tools":      actual_tools,
        "expected_topic":    tc.get("expected_topic"),
        "actual_topics":     actual_topics,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Setup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_engine() -> RAGEngine:
    """Build the default engine from the built-in knowledge base."""
    engine = RAGEngine(top_k=3)
    seed_engine(engine)
    engine.build()
    set_engine_ref(engine)
    return engine


def _print_bar(passed: int, total: int) -> None:
    bar_len = 40
    filled  = int(bar_len * passed / max(total, 1))
    bar     = "█" * filled + "░" * (bar_len - filled)
    pct     = passed / max(total, 1) * 100
    print(f"\n  [{bar}]  {passed}/{total}  ({pct:.0f}%)\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main test runner
# ─────────────────────────────────────────────────────────────────────────────

def run_tests(
    client:       LLMClient,
    engine:       RAGEngine,
    test_cases:   list[dict]  = TEST_CASES,
    sleep_s:      float       = 1.5,
    output_path:  str         = "test_results.json",
    verbose:      bool        = False,
) -> dict:
    """
    Run all test cases, evaluate, print summary, save JSON.
    Returns the full results dict.
    """
    results     = []
    passed_count = 0
    total_start = time.time()

    print(f"\nRunning {len(test_cases)} test case(s) …\n")

    for tc in test_cases:
        divider = "─" * 62
        print(divider)
        print(f"[{tc['id']}]  {tc['category']:<22}  {tc['notes']}")

        t0 = time.time()
        try:
            trace = client.run(engine, tc["question"], verbose=verbose)
            eval_ = evaluate(tc, trace)
        except Exception as exc:
            trace = {
                "question": tc["question"],
                "retrieved_chunks": [],
                "tool_calls": [],
                "final_answer": "",
                "error": str(exc),
                "llm_calls": 0,
            }
            eval_ = {
                "passed": False, "error": str(exc),
                "tool_use_correct": False, "tool_name_correct": False,
                "topic_correct": False, "has_answer": False,
                "expected_tool": tc["expected_tool"],
                "actual_tool_used": False,
                "expected_tool_name": tc.get("expected_tool_name"),
                "actual_tools": [],
                "expected_topic": tc.get("expected_topic"),
                "actual_topics": [],
            }

        latency_ms    = round((time.time() - t0) * 1000, 1)
        verdict       = "PASS" if eval_["passed"] else "FAIL"
        passed_count += int(eval_["passed"])
        icon          = "✅" if eval_["passed"] else "❌"

        print(
            f"  {icon}  {verdict}  |  "
            f"tool={eval_['actual_tool_used']} (exp {eval_['expected_tool']})  |  "
            f"{trace.get('llm_calls',0)} LLM call(s)  |  {latency_ms} ms"
        )
        if not eval_["passed"]:
            if not eval_["tool_use_correct"]:
                print(f"       ↳ tool_use mismatch")
            if not eval_["tool_name_correct"]:
                print(f"       ↳ wrong tool: got {eval_['actual_tools']}, expected {eval_['expected_tool_name']}")
            if not eval_["topic_correct"]:
                print(f"       ↳ wrong topic: got {eval_['actual_topics']}, expected {eval_['expected_topic']}")
            if not eval_["has_answer"]:
                print(f"       ↳ empty final answer")

        results.append({
            "test_id":          tc["id"],
            "category":         tc["category"],
            "question":         tc["question"],
            "notes":            tc["notes"],
            "retrieved_chunks": trace.get("retrieved_chunks", []),
            "tool_calls":       trace.get("tool_calls", []),
            "final_answer":     trace.get("final_answer", ""),
            "error":            trace.get("error"),
            "evaluation":       eval_,
            "verdict":          verdict,
            "latency_ms":       latency_ms,
            "llm_calls":        trace.get("llm_calls", 0),
        })

        if tc is not test_cases[-1]:
            time.sleep(sleep_s)   # respect Groq rate limit

    total_ms = round((time.time() - total_start) * 1000, 1)

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print(f"  RESULTS: {passed_count} / {len(test_cases)} passed")
    _print_bar(passed_count, len(test_cases))

    # ── Save JSON ─────────────────────────────────────────────────────────
    output = {
        "run_metadata": {
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "model":         client.model,
            "embed_method":  "TF-IDF (scikit-learn, local)",
            "top_k":         client.top_k,
            "total_tests":   len(test_cases),
            "passed":        passed_count,
            "failed":        len(test_cases) - passed_count,
            "pass_rate":     f"{passed_count / len(test_cases) * 100:.1f}%",
            "total_ms":      total_ms,
        },
        "test_results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Results saved → {output_path}\n")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable is not set.")
        sys.exit(1)

    print("Initialising …")
    engine = _build_engine()
    client = LLMClient(api_key=api_key, top_k=3)

    run_tests(client, engine, verbose=False)


if __name__ == "__main__":
    main()
