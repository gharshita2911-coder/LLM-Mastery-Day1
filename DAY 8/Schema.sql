-- =============================================================
-- Day 8 – Multi-step Workflow: Extract → Classify → Summarize → Store
-- DB Schema
-- =============================================================

CREATE TABLE IF NOT EXISTS tickets (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_text            TEXT    NOT NULL,

  -- Step 1: Extracted fields
  person              TEXT,                          -- reporter name
  company             TEXT,                          -- reporter company
  product             TEXT,                          -- product / service
  issue               TEXT,                          -- core problem phrase

  -- Step 2: Classification
  category            TEXT    CHECK(category IN ('bug','feature','question','complaint','other')),

  -- Step 3: Summary
  summary             TEXT,

  -- Token usage (accumulated across all LLM calls)
  prompt_tokens       INTEGER,
  candidates_tokens   INTEGER,
  total_tokens        INTEGER,

  -- Status & error tracking
  status              TEXT    NOT NULL DEFAULT 'success'
                              CHECK(status IN ('success','failed')),
  error_step          TEXT,                          -- 'extract' | 'classify' | 'summarize' | 'store'
  error_msg           TEXT,

  -- Timing
  latency_ms          INTEGER,
  created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_tickets_status   ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_created  ON tickets(created_at);

-- Overall run summary view
CREATE VIEW IF NOT EXISTS run_summary AS
SELECT
  COUNT(*)                                                          AS total_runs,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)              AS successful,
  SUM(CASE WHEN status = 'failed'  THEN 1 ELSE 0 END)              AS failed,
  ROUND(
    100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 1
  )                                                                 AS success_rate_pct,
  ROUND(AVG(latency_ms), 0)                                         AS avg_latency_ms,
  SUM(total_tokens)                                                  AS total_tokens_used
FROM tickets;

-- Category distribution view
CREATE VIEW IF NOT EXISTS category_breakdown AS
SELECT
    category,
    COUNT(*) AS count,
    ROUND(
        (
            100.0 * COUNT(*)
        ) / NULLIF(
            (
                SELECT COUNT(*)
                FROM tickets
                WHERE status = 'success'
            ),
            0
        ),
        1
    ) AS pct
FROM tickets
WHERE status = 'success'
GROUP BY category
ORDER BY count DESC;