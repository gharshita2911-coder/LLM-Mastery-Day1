# RAG Architecture & Runbooks

> **Phase 2 – RAG Engineering** | Owner: Both | Est: 4–6 hours  
> Last updated: 2025-06-02

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Component Reference](#2-component-reference)
3. [Indexing Runbook](#3-indexing-runbook)
4. [Query Runbook](#4-query-runbook)
5. [Scaling & Limits](#5-scaling--limits)
6. [Troubleshooting](#6-troubleshooting)
7. [Acceptance Criteria Checklist](#7-acceptance-criteria-checklist)

---

## 1. Architecture Overview

### 1.1 High-level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INDEXING PIPELINE                              │
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌─────────────────┐    ┌───────────┐  │
│  │ Raw Docs │───▶│  Chunker │───▶│ Embed Model     │───▶│JSON Store │  │
│  │(.txt/.md)│    │(512 tok, │    │(all-MiniLM-L6)  │    │index.json │  │
│  └──────────┘    │ 64 ovlp) │    │ 384-dim vectors │    └───────────┘  │
│                  └──────────┘    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           QUERY PIPELINE                                │
│                                                                         │
│  ┌──────────┐    ┌─────────────────┐    ┌──────────────┐               │
│  │ Question │───▶│  Embed Model    │───▶│ Cosine Sim   │               │
│  └──────────┘    │(all-MiniLM-L6)  │    │ Top-K Search │               │
│                  └─────────────────┘    └──────┬───────┘               │
│                                                │ top-K chunks          │
│                                         ┌──────▼───────┐               │
│                                         │ Context      │               │
│                                         │ Assembly     │               │
│                                         └──────┬───────┘               │
│                                                │ prompt                │
│                                         ┌──────▼───────┐               │
│                                         │  Groq LLM    │               │
│                                         │(llama3-70b)  │               │
│                                         └──────┬───────┘               │
│                                                │                       │
│                   ┌────────────────┐    ┌──────▼───────┐               │
│                   │query_results   │◀───│    Answer    │               │
│                   │    .json       │    └──────────────┘               │
│                   └────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow — Indexing

```
Document
  │
  ▼
read_text()          # src/indexer.py: index_file()
  │
  ▼
chunk_text()         # Word-count splitter, CHUNK_SIZE=512, CHUNK_OVERLAP=64
  │  produces list[str]
  ▼
embed_texts()        # SentenceTransformer.encode() → list[list[float]]
  │  384-dimensional vectors
  ▼
save_index()         # Append to data/index.json
  │
  ▼
data/index.json      # { metadata: {…}, chunks: [{id, source, text, embedding, …}] }
```

### 1.3 Data Flow — Querying

```
User Question (str)
  │
  ▼
embed_texts([question])        # Same model, same vector space
  │  query_vector: list[float]
  ▼
cosine_similarity(q, chunk_i)  # Against every chunk in index.json
  │  sorted descending by score
  ▼
Top-K chunks                   # TOP_K=5 by default
  │
  ▼
context_assembly()             # Concatenate [Source: …]\nchunk_text
  │
  ▼
groq.chat.completions.create() # llama3-70b-8192 with system+user prompt
  │
  ▼
answer (str)
  │
  ▼
append_result(result_dict)     # data/query_results.json
```

---

## 2. Component Reference

| Component | File | Purpose |
|-----------|------|---------|
| **Indexer** | `src/indexer.py` | Ingest docs → chunk → embed → store |
| **Query Engine** | `src/query.py` | Question → retrieve → generate → save |
| **Vector Store** | `data/index.json` | JSON flat-file; holds chunks + embeddings |
| **Results Store** | `data/query_results.json` | All query runs with full context + metrics |
| **Embed Model** | `all-MiniLM-L6-v2` | 384-dim sentence embeddings (local, CPU-OK) |
| **LLM** | Groq `llama3-70b-8192` | Answer generation via Groq API |
| **Indexer log** | `logs/indexer.log` | Timestamped indexing events |
| **Query log** | `logs/query.log` | Timestamped query events |

### 2.1 index.json Schema

```json
{
  "metadata": {
    "created_at": "2025-06-02T10:00:00Z",
    "updated_at": "2025-06-02T11:00:00Z",
    "chunks": 142
  },
  "chunks": [
    {
      "id":         "a1b2c3d4e5f6a7b8",
      "source":     "docs/handbook.md",
      "chunk_idx":  0,
      "text":       "Full text of the chunk …",
      "embedding":  [0.023, -0.154, …],
      "indexed_at": "2025-06-02T10:01:00Z",
      "metadata":   { "filename": "handbook.md" }
    }
  ]
}
```

### 2.2 query_results.json Schema

```json
[
  {
    "query_id":   "20250602T100523123456",
    "timestamp":  "2025-06-02T10:05:23Z",
    "question":   "What is the refund policy?",
    "answer":     "Refunds are processed within 5–7 business days …",
    "sources": [
      {
        "id":         "a1b2c3d4e5f6a7b8",
        "source":     "docs/handbook.md",
        "chunk_idx":  3,
        "similarity": 0.8712,
        "snippet":    "First 200 chars of chunk …"
      }
    ],
    "metrics": {
      "top_k":             5,
      "model":             "llama3-70b-8192",
      "prompt_tokens":     412,
      "completion_tokens": 187,
      "llm_latency_s":     1.24,
      "total_latency_s":   1.51
    }
  }
]
```

---

## 3. Indexing Runbook

### 3.1 Prerequisites

```bash
# 1. Clone repo and install deps
pip install -r requirements.txt

# 2. Set required environment variables
export GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxx"

# Optional overrides (defaults shown)
export CHUNK_SIZE=512
export CHUNK_OVERLAP=64
export INDEX_PATH="data/index.json"
export EMBED_MODEL="all-MiniLM-L6-v2"
```

### 3.2 Index New Documents

```bash
# Index a single file
python src/indexer.py docs/handbook.md

# Index multiple files at once
python src/indexer.py docs/*.md data/*.txt

# Index and REPLACE existing chunks for those sources (re-index)
python src/indexer.py docs/handbook.md --reindex
```

**What happens internally:**
1. Each file is read as UTF-8 text.
2. Text is split into ~512-word chunks with 64-word overlap.
3. All chunks are embedded in a single batch via `SentenceTransformer`.
4. New chunks (by SHA-256 hash) are appended to `data/index.json`.
5. A run summary is written to `data/last_index_run.json`.

### 3.3 Re-indexing After Document Changes

```bash
# Drop old chunks for a source and re-embed with fresh text
python src/indexer.py docs/updated_policy.md --reindex
```

> ⚠️ `--reindex` removes **all** existing chunks whose `source` field matches the file path. Use the exact same path as the original index run.

### 3.4 Programmatic Indexing (Python API)

```python
from src.indexer import index_document, index_file

# From a file path
result = index_file("docs/faq.md", reindex=False)
print(result)
# {'source': 'docs/faq.md', 'chunks_added': 12, 'chunks_skipped': 0, 'total_chunks': 154, 'duration_s': 2.3}

# From a raw string
result = index_document(
    text="Your raw document text here …",
    source="api-upload/doc-001",
    metadata={"author": "alice", "version": "2.1"},
)
```

### 3.5 Success Criteria

| Check | Expected |
|-------|----------|
| `data/index.json` exists | ✅ Created/updated |
| `metadata.chunks` count | > 0 and matches `len(chunks)` array |
| `data/last_index_run.json` | `chunks_added` > 0 for new docs |
| `logs/indexer.log` | Ends with `"Index saved"` line, no ERROR lines |
| Embedding dimension | Each `embedding` array has exactly 384 floats |

```bash
# Quick verification
python - <<'EOF'
import json
idx = json.load(open("data/index.json"))
print("Total chunks :", idx['metadata']['chunks'])
print("Vector dim   :", len(idx['chunks'][0]['embedding']))
print("Sources      :", {c['source'] for c in idx['chunks']})
EOF
```

### 3.6 Env Vars Reference (Indexer)

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `CHUNK_SIZE` | `512` | Words per chunk |
| `CHUNK_OVERLAP` | `64` | Overlapping words between chunks |
| `INDEX_PATH` | `data/index.json` | Path to vector store |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-Transformers model name |

---

## 4. Query Runbook

### 4.1 Prerequisites

Same as indexing. Additionally:

```bash
export GROQ_MODEL="llama3-70b-8192"   # or llama3-8b-8192 for speed
export TOP_K=5                         # chunks to retrieve per query
export RESULT_PATH="data/query_results.json"
```

### 4.2 Run a Query

```bash
# CLI
python src/query.py "What is the refund policy?"

# With custom top-k
python src/query.py "Summarise the onboarding process" --top-k 8

# Don't save to results file (testing)
python src/query.py "Quick test question" --no-save
```

**CLI output example:**

```
══════════════════════════════════════════════════════════════════════
❓ Question : What is the refund policy?
══════════════════════════════════════════════════════════════════════
💬 Answer   :
Refunds are processed within 5–7 business days of the approved
request. Items must be returned in original condition …
──────────────────────────────────────────────────────────────────────
📚 Sources  :
   [0.8712] docs/handbook.md (chunk 3)
   [0.8104] docs/faq.md (chunk 11)
──────────────────────────────────────────────────────────────────────
⚙  Metrics  : 5 chunks | llama3-70b-8192 | 412+187 tokens | 1.51s total
══════════════════════════════════════════════════════════════════════
✅  Full result saved → data/query_results.json
```

### 4.3 Programmatic Query (Python API)

```python
from src.query import query

result = query("What is the deployment process?", top_k=5)

print(result["answer"])
print(result["sources"][0]["similarity"])   # top similarity score
print(result["metrics"]["total_latency_s"]) # end-to-end seconds
```

### 4.4 Query Flow Step-by-Step

```
1. query(question)
   │
   ├─ retrieve(question, top_k)
   │    ├─ load_index()            → loads data/index.json into memory
   │    ├─ embed([question])       → 384-dim query vector
   │    └─ cosine_similarity(q,c)  → for every chunk c; sort desc; slice top_k
   │
   └─ generate_answer(question, top_chunks)
        ├─ Builds prompt: SYSTEM + context passages + question
        ├─ groq.chat.completions.create(model, messages, temperature=0.2)
        └─ Returns { answer, model, tokens, latency }

2. append_result(result) → data/query_results.json
```

### 4.5 Where to Check Logs

| Log file | What it contains |
|----------|-----------------|
| `logs/query.log` | Every query; retrieval chunk count; LLM token usage; latency |
| `logs/indexer.log` | All index operations |
| `data/query_results.json` | Full structured output of every query run |

```bash
# Tail live query logs
tail -f logs/query.log

# See last 5 queries with answers (requires jq)
jq '.[-5:] | .[] | {q: .question, a: .answer[:120]}' data/query_results.json

# Check average latency of last 20 queries
jq '[.[-20:][].metrics.total_latency_s] | add/length' data/query_results.json
```

### 4.6 Env Vars Reference (Query)

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `GROQ_MODEL` | `llama3-70b-8192` | Groq chat model |
| `TOP_K` | `5` | Chunks retrieved per query |
| `INDEX_PATH` | `data/index.json` | Path to vector store |
| `RESULT_PATH` | `data/query_results.json` | Append-only results log |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Must match model used at index time |

---

## 5. Scaling & Limits

### 5.1 Current Architecture Limits

| Dimension | Limit | Notes |
|-----------|-------|-------|
| Index size | ~50 k chunks practical | JSON load time grows linearly; >100 k → migrate to vector DB |
| Embedding throughput | ~500 chunks/min on CPU | Use GPU or batch API for large ingestion jobs |
| Query latency | 1–3 s typical | ~0.3 s retrieval + ~1–2 s Groq LLM |
| Concurrency | 1 write at a time | JSON file write is not thread-safe; serialize writes or use a DB |
| Groq rate limits | Varies by plan | Check [console.groq.com](https://console.groq.com) for your tier limits |
| Context window | 8 192 tokens (llama3-70b) | Reduce TOP_K or CHUNK_SIZE if hitting limit |

### 5.2 Scaling Path

```
Current (JSON flat-file)
  └─ Good for: prototyping, <50 k chunks, single process

Next step (FAISS or ChromaDB)
  ├─ Replace save_index/load_index + cosine_similarity
  │  with FAISS IndexFlatIP or Chroma collection
  └─ Keeps the same chunker + Groq LLM layer unchanged

Production (Pinecone / Qdrant / Weaviate)
  ├─ Add metadata filtering (by source, date, tags)
  ├─ Horizontal read replicas
  └─ Async indexing queue (Celery / RQ)
```

### 5.3 Tuning Levers

| Lever | Effect |
|-------|--------|
| Increase `CHUNK_SIZE` | Fewer chunks, more context per chunk, higher token cost |
| Decrease `CHUNK_SIZE` | More precise retrieval, lower token cost per chunk |
| Increase `CHUNK_OVERLAP` | Better boundary handling, more chunks stored |
| Increase `TOP_K` | More context → better recall, higher token cost |
| Switch to `llama3-8b-8192` | 2–3× faster, lower quality |
| Switch to `mixtral-8x7b-32768` | 32 k context window, slower |

---

## 6. Troubleshooting

### Scenario 1 — `GROQ_API_KEY` not set

**Symptom:** `EnvironmentError: GROQ_API_KEY is not set.`

**Fix:**
```bash
export GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxx"
# Or add to .env and source it:
echo 'GROQ_API_KEY=gsk_xxx' >> .env && source .env
```

---

### Scenario 2 — Index is empty / `FileNotFoundError`

**Symptom:**  
`FileNotFoundError: Index not found at data/index.json. Run indexer.py first.`  
or  
`ValueError: Index is empty. Please index some documents first.`

**Fix:**
```bash
# Verify index exists and has chunks
ls -lh data/index.json
python -c "import json; d=json.load(open('data/index.json')); print(d['metadata'])"

# If missing, index at least one document
python src/indexer.py your_document.md
```

---

### Scenario 3 — Very low similarity scores (all chunks < 0.3)

**Symptom:** Answers are irrelevant or LLM says "I don't have enough context."

**Diagnosis:**
```bash
# Check if EMBED_MODEL at query time matches index time
grep "EMBED_MODEL" logs/indexer.log | tail -1
grep "EMBED_MODEL" logs/query.log  | tail -1
```

**Fix options:**
1. Ensure `EMBED_MODEL` is **identical** at index and query time.
2. If the question domain differs from indexed docs, add more relevant documents.
3. Rephrase the question to match vocabulary in the documents.
4. Increase `TOP_K` to cast a wider net.

---

### Scenario 4 — Groq API rate limit / 429 error

**Symptom:** `groq.RateLimitError: 429 Too Many Requests`

**Fix:**
```bash
# Add exponential backoff (manual retry):
python -c "
import time
from src.query import query

for attempt in range(3):
    try:
        result = query('Your question here')
        break
    except Exception as e:
        if '429' in str(e):
            wait = 2 ** attempt
            print(f'Rate limited, waiting {wait}s…')
            time.sleep(wait)
        else:
            raise
"
```

For bulk querying, add `time.sleep(1)` between calls or upgrade your Groq plan.

---

### Scenario 5 — Groq context window exceeded

**Symptom:** `groq.BadRequestError: … maximum context length exceeded`

**Fix:** Reduce the amount of context sent to the LLM.

```bash
# Option A: Reduce TOP_K
export TOP_K=3
python src/query.py "Your question"

# Option B: Reduce CHUNK_SIZE (requires re-indexing)
export CHUNK_SIZE=256
python src/indexer.py docs/*.md --reindex

# Option C: Switch to a larger context model
export GROQ_MODEL="mixtral-8x7b-32768"
python src/query.py "Your question"
```

---

## 7. Acceptance Criteria Checklist

| Criterion | Status |
|-----------|--------|
| ✅ Architecture described (ingest + query flows with diagram) | Done |
| ✅ Indexing runbook (commands, env vars, success criteria) | Done |
| ✅ Query runbook (flow, testing commands, log locations) | Done |
| ✅ Scaling limits documented | Done |
| ✅ 5 troubleshooting scenarios | Done |
| ✅ Another developer could operate from this doc alone | Done |

---

## Appendix — Quick-Start Cheat Sheet

```bash
# ── Setup ────────────────────────────────────────────────────────────
pip install -r requirements.txt
export GROQ_API_KEY="gsk_xxxx"

# ── Index ────────────────────────────────────────────────────────────
python src/indexer.py docs/my_doc.md              # index a file
python src/indexer.py docs/*.md --reindex         # re-index all

# Verify
python -c "import json; d=json.load(open('data/index.json')); print(d['metadata'])"

# ── Query ────────────────────────────────────────────────────────────
python src/query.py "What is the refund policy?"
python src/query.py "Explain onboarding" --top-k 8

# ── Inspect results ──────────────────────────────────────────────────
jq '.[-1]' data/query_results.json                # last query
tail -f logs/query.log                            # live log

# ── Troubleshoot ─────────────────────────────────────────────────────
grep ERROR logs/indexer.log
grep ERROR logs/query.log
```
