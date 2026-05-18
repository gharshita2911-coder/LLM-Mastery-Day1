"""
pipeline.py – Orchestrator
============================
Chains the four steps for a single raw text input.

  Step 1  extractor.step1_extract     Gemini structured output → person, company, product, issue + tokens
  Step 2  classifier.step2_classify   Regex rules + Gemini fallback → category + tokens
  Step 3  summarizer.step3_summarize  Gemini one-liner → summary + tokens
  Step 4  db.step4_store              INSERT → id, created_at, row_count

Token counts from all LLM calls are accumulated into one Completion object.
On any step failure the pipeline short-circuits and the partial record is
persisted with status='failed', error_step, and error_msg.
"""

import time

from config import Completion, TicketRecord
from db import step4_store
from extractor import step1_extract
from classifier import step2_classify
from summariser import step3_summarise


def _accumulate(base: Completion, addition: Completion) -> Completion:
    """Add two Completion token counts together."""
    def _add(a, b):
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)
    return Completion(
        prompt_token_count=     _add(base.prompt_token_count,     addition.prompt_token_count),
        candidates_token_count= _add(base.candidates_token_count, addition.candidates_token_count),
        total_token_count=      _add(base.total_token_count,      addition.total_token_count),
    )


def process_ticket(raw_text: str) -> TicketRecord:
    """
    Run *raw_text* through the full four-step pipeline.
    Always returns a TicketRecord with all fields populated.
    """
    record = TicketRecord(raw_text=raw_text)
    start  = time.time()

    # ── Step 1: Extract ───────────────────────────────────────────────────────
    try:
        extracted, c1          = step1_extract(raw_text)
        record.person          = extracted.get("person")
        record.company         = extracted.get("company")
        record.product         = extracted.get("product")
        record.issue           = extracted.get("issue")
        record.completion      = _accumulate(record.completion, c1)
    except Exception as exc:
        return _fail(record, start, "extract", exc)

    # ── Step 2: Classify ──────────────────────────────────────────────────────
    try:
        category, c2           = step2_classify(raw_text, extracted)
        record.category        = category or "other"
        record.completion      = _accumulate(record.completion, c2)
    except Exception as exc:
        return _fail(record, start, "classify", exc)

    # ── Step 3: Summarize ─────────────────────────────────────────────────────
    try:
        summary, c3            = step3_summarise(raw_text, record.category)
        record.summary         = summary
        record.completion      = _accumulate(record.completion, c3)
    except Exception as exc:
        return _fail(record, start, "summarize", exc)

    # ── Step 4: Store ─────────────────────────────────────────────────────────
    try:
        record.latency_ms = int((time.time() - start) * 1000)
        row_id, created_at, row_count = step4_store(record)
        record.id         = row_id
        record.created_at = created_at
        record.row_count  = row_count
    except Exception as exc:
        record.status     = "failed"
        record.error_step = "store"
        record.error_msg  = str(exc)
        try:
            row_id, created_at, row_count = step4_store(record)
            record.id         = row_id
            record.created_at = created_at
            record.row_count  = row_count
        except Exception:
            pass

    return record


def _fail(record: TicketRecord, start: float, step: str, exc: Exception) -> TicketRecord:
    record.status     = "failed"
    record.error_step = step
    record.error_msg  = str(exc)
    record.latency_ms = int((time.time() - start) * 1000)
    try:
        row_id, created_at, row_count = step4_store(record)
        record.id         = row_id
        record.created_at = created_at
        record.row_count  = row_count
    except Exception:
        pass
    return record