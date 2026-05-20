# Groq Model Comparison Report

> **Generated:** 2026-05-20  
> **Models:** llama-3.3-70b-versatile, llama-3.1-8b-instant  
> **Prompts:** 15 across 6 categories  
> **Metric baseline:** Groq public pricing, temperature = 0 (deterministic)

## 1. Summary Comparison Table

| Metric | `llama-3.3-70b-versatile` | `llama-3.1-8b-instant` |
|--------|:-----------------:|:----------------:|
| **Avg latency (s)** | 0.836s | 1.403s |
| **Median latency (s)** | 0.736s | 0.658s |
| **Max latency (s)** | 1.790s | 7.181s |
| **Avg cost / request** | $0.000202 | $0.000021 |
| **Total cost (all prompts)** | $0.003033 | $0.000309 |
| **Avg input tokens** | 61 | 61 |
| **Avg output tokens** | 210 | 220 |
| **Quality score (avg /3)** | 3.00 | 3.00 |
| **Quality pass rate** | 100.0% | 100.0% |
| **Errors** | 0 | 0 |

## 2. Pricing Reference

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|:--------------------:|:----------------------:|
| `llama-3.3-70b-versatile` | $0.59 | $0.79 |
| `llama-3.1-8b-instant` | $0.05 | $0.08 |

## 3. Per-Category Breakdown

| Category | 70B avg lat (s) | 8B avg lat (s) | 70B quality | 8B quality |
|----------|:--------------:|:--------------:|:-----------:|:----------:|
| Factual | 0.879s | 0.578s | 3.0/3 | 3.0/3 |
| Reasoning | 1.113s | 0.671s | 3.0/3 | 3.0/3 |
| Coding | 1.146s | 2.960s | 3.0/3 | 3.0/3 |
| Summarisation | 0.569s | 3.164s | 3.0/3 | 3.0/3 |
| Creative | 0.380s | 0.433s | 3.0/3 | 3.0/3 |
| Instruction | 0.614s | 0.611s | 3.0/3 | 3.0/3 |

## 4. Per-Prompt Detail

| Prompt | Category | Model | Latency (s) | In tok | Out tok | Cost (USD) | Quality |
|--------|----------|-------|:-----------:|:------:|:-------:|:----------:|:-------:|
| P01 | Factual | `llama-3.3-70b-versatile` | 0.719 | 48 | 52 | $0.000069 | 3/3 |
| P01 | Factual | `llama-3.1-8b-instant` | 0.176 | 48 | 29 | $0.000005 | 3/3 |
| P02 | Factual | `llama-3.3-70b-versatile` | 1.449 | 47 | 512 | $0.000432 | 3/3 |
| P02 | Factual | `llama-3.1-8b-instant` | 1.104 | 47 | 482 | $0.000041 | 3/3 |
| P03 | Factual | `llama-3.3-70b-versatile` | 0.468 | 46 | 96 | $0.000103 | 3/3 |
| P03 | Factual | `llama-3.1-8b-instant` | 0.455 | 46 | 45 | $0.000006 | 3/3 |
| P04 | Reasoning | `llama-3.3-70b-versatile` | 0.792 | 70 | 154 | $0.000163 | 3/3 |
| P04 | Reasoning | `llama-3.1-8b-instant` | 0.321 | 70 | 144 | $0.000015 | 3/3 |
| P05 | Reasoning | `llama-3.3-70b-versatile` | 0.757 | 66 | 228 | $0.000219 | 3/3 |
| P05 | Reasoning | `llama-3.1-8b-instant` | 0.658 | 66 | 200 | $0.000019 | 3/3 |
| P06 | Reasoning | `llama-3.3-70b-versatile` | 1.790 | 76 | 448 | $0.000399 | 3/3 |
| P06 | Reasoning | `llama-3.1-8b-instant` | 1.033 | 76 | 454 | $0.000040 | 3/3 |
| P07 | Coding | `llama-3.3-70b-versatile` | 0.764 | 64 | 192 | $0.000189 | 3/3 |
| P07 | Coding | `llama-3.1-8b-instant` | 0.728 | 64 | 354 | $0.000032 | 3/3 |
| P08 | Coding | `llama-3.3-70b-versatile` | 1.142 | 57 | 465 | $0.000401 | 3/3 |
| P08 | Coding | `llama-3.1-8b-instant` | 0.971 | 57 | 482 | $0.000041 | 3/3 |
| P09 | Coding | `llama-3.3-70b-versatile` | 1.533 | 54 | 470 | $0.000403 | 3/3 |
| P09 | Coding | `llama-3.1-8b-instant` | 7.181 | 54 | 512 | $0.000044 | 3/3 |
| P10 | Summarisation | `llama-3.3-70b-versatile` | 0.434 | 106 | 89 | $0.000133 | 3/3 |
| P10 | Summarisation | `llama-3.1-8b-instant` | 0.523 | 106 | 72 | $0.000011 | 3/3 |
| P11 | Summarisation | `llama-3.3-70b-versatile` | 0.704 | 58 | 143 | $0.000147 | 3/3 |
| P11 | Summarisation | `llama-3.1-8b-instant` | 5.806 | 58 | 174 | $0.000017 | 3/3 |
| P12 | Creative | `llama-3.3-70b-versatile` | 0.477 | 43 | 59 | $0.000072 | 3/3 |
| P12 | Creative | `llama-3.1-8b-instant` | 0.391 | 43 | 47 | $0.000006 | 3/3 |
| P13 | Creative | `llama-3.3-70b-versatile` | 0.283 | 54 | 12 | $0.000041 | 3/3 |
| P13 | Creative | `llama-3.1-8b-instant` | 0.476 | 54 | 15 | $0.000004 | 3/3 |
| P14 | Instruction | `llama-3.3-70b-versatile` | 0.736 | 60 | 125 | $0.000134 | 3/3 |
| P14 | Instruction | `llama-3.1-8b-instant` | 0.669 | 60 | 171 | $0.000017 | 3/3 |
| P15 | Instruction | `llama-3.3-70b-versatile` | 0.491 | 65 | 112 | $0.000127 | 3/3 |
| P15 | Instruction | `llama-3.1-8b-instant` | 0.553 | 65 | 113 | $0.000012 | 3/3 |

## 5. Quality Notes

Prompts where at least one model lost a quality point:

_All responses passed quality checks._

## 6. Recommendation

**llama-3.3-70b-versatile** costs **9.6x** more and is **0.6x** slower
than **llama-3.1-8b-instant**, while scoring **0.0 percentage points**
higher on quality.

### Use `llama-3.1-8b-instant` when
- **Budget is the primary constraint** - up to 10x cheaper per token.
- Tasks are **simple, structured, or templated** (classification, extraction, short Q&A).
- **Latency matters** more than depth - faster responses for real-time UX.

### Use `llama-3.3-70b-versatile` when
- Tasks require **multi-step reasoning**, code generation, or nuanced writing.
- **Quality consistency** across edge cases is more valuable than cost savings.
- You can afford slightly higher latency for a **production-critical** path.

### Hybrid approach (recommended)
Route simple/templated prompts to **llama-3.1-8b-instant**, complex/agentic prompts to **llama-3.3-70b-versatile**. This typically yields **70-80% cost savings** with minimal quality loss on the overall pipeline.

---
*Report generated by `generate_report.py`. Re-run after any pricing or prompt changes.*