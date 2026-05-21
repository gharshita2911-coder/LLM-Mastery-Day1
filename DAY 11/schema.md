# RAG System — Schema Documentation

**Version:** 1.0
**Generated from:** `rag_schema.py`, `rag_engine.py`, `app.py`, `retriever.py`, `test_runner.py`

---

## Response Schema

Every RAG response is validated against this contract — server-side via Pydantic and independently re-validated client-side by the test runner.

### Core Structure

```json
{
  "answer":     "string",
  "confidence": "high | medium | low",
  "sources": [
    {
      "chunkId": "string",
      "snippet": "string"
    }
  ]
}
```

### Field Definitions

#### `answer`
| Property | Value |
|---|---|
| Type | `string` |
| Required | Yes |
| Constraint | Non-empty, non-whitespace |
| Description | Complete sentence(s) answering the user query |

#### `confidence`
| Property | Value |
|---|---|
| Type | `enum` |
| Required | Yes |
| Allowed values | `high`, `medium`, `low` |

**Rules:**
- `high` — 2+ chunks directly answer the query
- `medium` — 1 chunk supports it, or evidence is indirect
- `low` — evidence is weak, tangential, or fallback was used

#### `sources`
| Property | Value |
|---|---|
| Type | `array` |
| Required | Yes |
| Min items | 1 |

Each source item:

| Field | Type | Required | Description |
|---|---|---|---|
| `chunkId` | string | Yes | Must match a real chunk ID from the knowledge base (e.g. `py-001`, `ml-003`, `rag-002`) |
| `snippet` | string | Yes | 15–60 word verbatim excerpt from the retrieved chunk |

---

## Pydantic Models

Defined in `rag_schema.py`:

```python
class SourceChunk(BaseModel):
    chunkId: str = Field(...)
    snippet: str = Field(...)

class RAGStructuredOutput(BaseModel):
    answer:     str
    confidence: Literal["high", "medium", "low"]
    sources:    list[SourceChunk]
```

---

## Full API Response

Returned by `run_rag_query()` and both `/rag` and `/rag/batch` endpoints:

| Field | Type | Description |
|---|---|---|
| `query` | string | Original user question |
| `answer` | string | LLM-generated answer |
| `confidence` | string | `high` \| `medium` \| `low` |
| `sources` | array | `[{ chunkId, snippet }]` |
| `valid` | bool | `true` if schema-valid (including fallback responses) |
| `attempts` | int | Number of LLM calls made (1–3) |
| `used_fallback` | bool | `true` if all LLM attempts failed and chunk text was used directly |
| `error` | string \| null | Last error message if retries were needed |
| `chunks_retrieved` | array | `[{ chunkId, doc, score }]` — top-k TF-IDF results |

---

## Batch Endpoint

### `POST /rag/batch`

**Request body:**
```json
{
  "queries": ["question 1", "question 2"],
  "top_k": 3
}
```

**Response body:**
| Field | Type | Description |
|---|---|---|
| `total` | int | Number of queries processed |
| `valid_count` | int | Responses passing schema validation |
| `invalid_count` | int | Responses failing schema validation |
| `valid_pct` | float | `valid_count / total × 100` |
| `target_met` | bool | `true` if `valid_pct >= 95.0` |
| `results` | array | One full API response per query |

---

## Other Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — returns `status`, `groq_key_set`, `model` |
| `POST` | `/rag` | Single query — body: `{ "query": "string" }` |
| `POST` | `/rag/batch` | Batch queries — body: `{ queries, top_k }` |

---

## Validation Pipeline

```
LLM call (temperature=0.0)
    │
    ├─ _extract_json()
    │     1. Direct JSON parse
    │     2. Strip markdown fences → parse
    │     3. Find first { ... } block → parse
    │
    ├─ Pydantic RAGStructuredOutput(**data)   ← server-side validation
    │
    ├─ PASS ──────────────────────────────── return response  ✓  valid=true
    │
    └─ FAIL → retry (up to MAX_RETRIES=2, delay=1.5s between each)
                  │
                  └─ All 3 attempts failed
                           │
                           └─ _build_fallback()               ← always schema-valid
                                 answer     = first 400 chars of top-2 chunks
                                 confidence = "low"
                                 sources    = first 150 chars of top-2 chunks
                                 valid      = true
                                 used_fallback = true
```

After server validation, `test_runner.py` independently re-validates every field client-side via `_validate_result()`.

---

## Retriever

**File:** `retriever.py`
**Algorithm:** TF-IDF (pure Python stdlib — no external dependencies)
**Default top-k:** 3

**Scoring formula:**
```
score = Σ  TF(term, query) × TF(term, chunk) × IDF(term)
         term ∈ (query_tokens ∪ chunk_tokens)
```

**Output fields per chunk:** `chunkId`, `doc`, `text`, `score`

---

## Knowledge Base

**File:** `knowledge_base.py`
**Total chunks:** 20

### Chunk ID Format

`<topic>-<NNN>` — e.g. `py-001`, `ml-003`, `rag-002`, `se-004`, `cloud-001`

### Topics

| Prefix | Topic | Chunk IDs |
|---|---|---|
| `py` | Python | `py-001` – `py-004` |
| `ml` | Machine Learning | `ml-001` – `ml-004` |
| `rag` | RAG & LLMs | `rag-001` – `rag-004` |
| `se` | Software Engineering | `se-001` – `se-004` |
| `cloud` | Cloud Computing | `cloud-001` – `cloud-002` |
| `devops` | DevOps & Containers | `devops-001` – `devops-002` |

### Chunk Fields

| Field | Type | Description |
|---|---|---|
| `chunkId` | string | Unique identifier |
| `doc` | string | Document / section title |
| `text` | string | Full chunk content |

---

## Test Run Results

**Last run:** `2026-05-21T08:14:38Z`
**File:** `rag_test_summary.json`

| Metric | Value |
|---|---|
| Total queries | 20 |
| Valid responses | 20 (100%) |
| Invalid responses | 0 |
| Target ≥95% met | ✅ Yes |
| Fallbacks used | 20 |
| Avg LLM attempts | 3.0 |
| Confidence — high | 0 |
| Confidence — medium | 0 |
| Confidence — low | 20 |

---

## ⚠ Known Issue: Fallback Overuse

| Property | Detail |
|---|---|
| **Symptom** | `fallback_used_count: 20`, `avg_attempts: 3.0` |
| **Cause** | LLM is not returning clean JSON despite `temperature=0.0` |
| **Impact** | Schema validity = 100% but all answers are raw chunk excerpts with `confidence=low`, not synthesised LLM responses |
| **Suggested fix** | Add a one-shot JSON example to the system prompt, or switch to a larger model (`llama3-70b-8192`) |

