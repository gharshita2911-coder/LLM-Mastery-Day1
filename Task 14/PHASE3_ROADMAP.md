# Phase 3 Roadmap — Static RAG → Production Evolution

**Based on:** Task 14 — Static RAG with TF-IDF (CLI-based)
**Current state:** CLI test runner, hardcoded 24 chunks, TF-IDF retrieval, Groq LLM, guardrails, evaluator
**Goal:** Evolve this codebase into a production-ready document Q&A system

---

## 🎯 Overview: Task 14 vs Task 15

Task 14 is the **foundation** — it proves the RAG pipeline works with a controlled dataset.
Task 15 is the **evolution** — it adds dynamic document upload, vector search, and a FastAPI server.

This roadmap covers both paths:
- **Path A:** Evolve Task 14 directly (add features here)
- **Path B:** Use learnings from Task 14 to enhance Task 15 (already started)

---

## Phase 3 Milestones Overview

| Milestone | Effort | Priority |
|-----------|--------|----------|
| M1 — Vector Search Upgrade (TF-IDF → ChromaDB) | 4-6 hrs | 🔴 P0 |
| M2 — FastAPI REST API Layer | 4-6 hrs | 🔴 P0 |
| M3 — Advanced Retrieval | 6-8 hrs | 🟡 P1 |
| M4 — Production Hardening | 4-6 hrs | 🟡 P1 |
| M5 — Observability & Monitoring | 4-6 hrs | 🟡 P1 |
| M6 — Knowledge Base Expansion | 4-6 hrs | 🟢 P2 |
| M7 — Multi-Turn Conversations | 6-8 hrs | 🟢 P2 |

---

## M1 — Vector Search Upgrade ⏰ 4-6 hrs

### Current state (Task 14):
```python
# knowledge_base.py — TF-IDF with in-memory Counters
from collections import Counter

def retrieve(query, top_k=5):
    query_vec = _compute_tfidf_vector(_tokenize(query), _IDF)
    scored = [(_cosine_similarity(query_vec, doc_vec), i) for i, doc_vec in enumerate(_DOC_VECTORS)]
    scored.sort(reverse=True)
    return scored[:top_k]
```

### Target (Phase 3):
Replace TF-IDF with **embeddings + ChromaDB** for semantic search.

### Tasks:

#### 1.1 Add embedding model (1 hr)
```python
# retrieval/embeddings.py
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str) -> list[float]:
    return _model.encode(text).tolist()

def embed_batch(texts: list[str]) -> list[list[float]]:
    return _model.encode(texts).tolist()
```

#### 1.2 Set up ChromaDB (1 hr)
```python
# retrieval/vector_store.py
import chromadb

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(name="knowledge_base")

# Pre-compute embeddings for all 24 chunks
for chunk in _DOCUMENTS:
    collection.add(
        ids=[chunk["chunkId"]],
        embeddings=[embed(chunk["text"])],
        documents=[chunk["text"]],
        metadatas=[{"category": chunk["category"]}],
    )
```

#### 1.3 Update retrieval (1 hr)
```python
def retrieve(query: str, top_k: int = 5) -> list[dict]:
    query_emb = embed(query)
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    # Format results same as current API for backward compatibility
    ...
```

#### 1.4 Migration script (1 hr)
```python
# scripts/migrate_to_vector.py
"""One-time migration: embed all 24 chunks into ChromaDB"""
from knowledge_base import get_all_chunks
from retrieval.vector_store import VectorStore
```

#### 1.5 Keep TF-IDF as fallback (1 hr)
```python
# retrieval/hybrid.py
def retrieve(query, top_k=5):
    vector_results = vector_search(query, top_k)
    if not vector_results:
        return tfidf_search(query, top_k)  # Fallback
    return vector_results
```

**Files to create:**
```
retrieval/
├── __init__.py
├── embeddings.py
├── vector_store.py
└── hybrid.py
scripts/
└── migrate_to_vector.py
```

---

## M2 — FastAPI REST API Layer ⏰ 4-6 hrs

### Current state:
```bash
# CLI-only
python3 test_runner.py
```

### Target:
```bash
# REST API
curl http://localhost:8000/rag/query -d '{"query":"password policy"}'
```

### Tasks:

#### 2.1 Create FastAPI server (1.5 hrs)
```python
# api/main.py
from fastapi import FastAPI
from rag_engine import run_rag_query

app = FastAPI(title="RAG API")

@app.post("/rag/query")
async def query(request: QueryRequest):
    result = run_rag_query(request.query, top_k=request.top_k)
    return result

@app.post("/rag/batch")
async def batch_query(queries: list[str]):
    return [run_rag_query(q) for q in queries]
```

#### 2.2 Preserve existing endpoints from Task 15 (1 hr)
```
GET  /health
POST /rag/query
POST /rag/batch
GET  /stats
DELETE /clear
```

#### 2.3 Add interactive docs (0.5 hr)
FastAPI auto-generates `/docs` — just ensure request/response models are well-documented with Pydantic.

#### 2.4 Request/Response models (1 hr)
```python
# api/models.py
from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    model: Optional[str] = None  # Override default model

class QueryResponse(BaseModel):
    query_id: str
    answer: str
    confidence: str
    sources: list
    elapsed_seconds: float
    cost_usd: float
```

#### 2.5 Keep CLI as alternative (1 hr)
- `test_runner.py` should work with `--host` flag to point at API or run locally
- Support both modes: `python3 test_runner.py` (standalone) and `python3 test_runner.py --host http://localhost:8000` (API mode)

**Files to create:**
```
api/
├── __init__.py
├── main.py
├── models.py
└── router.py
```

---

## M3 — Advanced Retrieval ⏰ 6-8 hrs

### 3.1 Hybrid Search (TF-IDF + Vector) (2 hrs)
Combine both methods:
```python
def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    vector_results = vector_search(query, top_k * 2)
    keyword_results = tfidf_search(query, top_k * 2)
    
    # Reciprocal Rank Fusion
    return rrf_merge(vector_results, keyword_results)
```

### 3.2 Metadata Filtering (1 hr)
Add category-based filtering to the existing 24 chunks:
```
POST /rag/query
{
  "query": "password policy",
  "filters": {"category": "Security & Compliance"}
}
```

### 3.3 Query Expansion (1.5 hrs)
Generate 3 query variations using Groq to improve recall:
```python
def expand_query(query: str) -> list[str]:
    prompt = f"Generate 3 alternative phrasings of: {query}"
    variations = groq_client.chat(...)
    return [query] + variations
```

### 3.4 Re-ranking with Cross-Encoder (1.5 hrs)
```python
from sentence_transformers import CrossEncoder
ranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, chunks: list[dict]) -> list[dict]:
    pairs = [(query, c["text"]) for c in chunks]
    scores = ranker.predict(pairs)
    for c, s in zip(chunks, scores):
        c["rerank_score"] = float(s)
    return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
```

### 3.5 Chunking Improvement (1 hr)
Improve the existing 24 chunks:
- Add more chunks (target: 100+ covering real IT policies)
- Use semantic chunking with overlap
- Add hierarchical structure (Document → Section → Chunk)

---

## M4 — Production Hardening ⏰ 4-6 hrs

### 4.1 Configuration Profiles (1 hr)
```python
# config.py
import os

ENV = os.getenv("RAG_ENV", "development")

if ENV == "production":
    RAG_MODEL = "llama-3.1-70b-versatile"  # More capable
    LATENCY_TARGET = 5.0  # More relaxed
    LOG_LEVEL = "WARNING"
elif ENV == "development":
    RAG_MODEL = "llama-3.1-8b-instant"
    LATENCY_TARGET = 3.0
    LOG_LEVEL = "DEBUG"
```

### 4.2 Structured Logging (1 hr)
```python
import structlog
logger = structlog.get_logger()
logger.info("rag_query", query_id="Q001", latency=0.5, cost=0.00003)
```

### 4.3 Rate Limiting & Auth (1 hr)
```python
# For API mode
from slowapi import Limiter
limiter = Limiter(key_func=lambda: request.client.host)
```

### 4.4 Error Standardization (1 hr)
All errors return consistent format:
```json
{
  "error": {
    "code": "CHUNK_NOT_FOUND",
    "message": "No relevant chunks retrieved",
    "details": {"query": "..."}
  }
}
```

### 4.5 Graceful Degradation (1 hr)
- If ChromaDB is down → fallback to TF-IDF
- If Groq API fails → use cached responses
- If all fails → return safe default message

---

## M5 — Observability & Monitoring ⏰ 4-6 hrs

### 5.1 Test Result Dashboard (1.5 hrs)
Enhance `test_results.json` output with a simple HTML report:
```python
def generate_report(results: list[dict]) -> str:
    """Generate an HTML report from test results"""
    # Table with per-query results
    # Summary charts (PASS/FAIL pie, latency histogram)
    # Cost breakdown
```

### 5.2 LangFuse Tracing (1.5 hrs)
```python
from langfuse import Langfuse
langfuse = Langfuse()

with langfuse.trace(name="rag_query") as trace:
    trace.span(name="retrieval", input=query, output=chunks)
    trace.span(name="generation", input=prompt, output=answer, usage=usage)
```

### 5.3 Prometheus Metrics (1 hr)
```python
from prometheus_client import Counter, Histogram

RAG_QUERIES = Counter("rag_queries_total", "Total RAG queries")
RAG_LATENCY = Histogram("rag_latency_seconds", "Query latency")
RAG_COST = Counter("rag_cost_usd", "Total cost")
```

### 5.4 Comparative Analysis Tool (1 hr)
Compare results across different configurations:
```bash
python3 compare_configs.py --model1 llama-3.1-8b-instant --model2 llama3-8b-8192
```
Output a side-by-side comparison of latency, cost, and confidence.

---

## M6 — Knowledge Base Expansion ⏰ 4-6 hrs

### 6.1 Add More IT Topics (2 hrs)
Expand the 24 hardcoded chunks to cover:
- Cloud services (AWS, Azure, GCP access)
- DevOps tools (Docker, Kubernetes, CI/CD)
- Database access and management
- Remote work policies
- Equipment return process
- Conference room booking
- Parking and building access
- Emergency procedures

**Target:** 100+ chunks across 15+ categories

### 6.2 Multi-Language Support (1 hr)
Add chunks in different languages:
```python
_DOCUMENTS.extend([
    {
        "chunkId": "chunk_025",
        "category": "Password & Account",
        "language": "es",
        "text": "Las contraseñas deben tener al menos 12 caracteres..."
    },
])
```
Query with `?lang=es` to restrict retrieval by language.

### 6.3 Version Controlled Knowledge Base (1 hr)
- Store chunks as JSON files in `knowledge/` directory
- Git-trackable, reviewable changes
- Auto-load all chunks from directory on startup

### 6.4 Knowledge Base Editor (1 hr)
Simple CLI tool to add/edit/delete chunks:
```bash
python3 manage_kb.py add --category "Network" --text "..."
python3 manage_kb.py list --category "Security"
python3 manage_kb.py delete chunk_012
```

---

## M7 — Multi-Turn Conversations ⏰ 6-8 hrs

### 7.1 Conversation Buffer (2 hrs)
```python
# conversation/history.py
from collections import deque

class ConversationBuffer:
    def __init__(self, max_turns=5):
        self.history = deque(maxlen=max_turns * 2)
    
    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
    
    def get_context(self) -> str:
        return "\n".join(f"{m['role']}: {m['content']}" for m in self.history)
```

### 7.2 Query Rephrasing (2 hrs)
When user asks a follow-up, rewrite it to be self-contained:
```
User: "What about VPN?"
Context: Previous Q&A about Wi-Fi
Rewritten: "What is the corporate VPN setup and how do I connect?"
```

### 7.3 Context-Aware Retrieval (1 hr)
Include conversation summary in the retrieval query:
```python
def retrieve_with_context(query: str, history: list[dict]) -> list[dict]:
    # First rephrase query with context
    full_query = rephrase_query(query, history)
    # Then retrieve with expanded query
    return retrieve(full_query)
```

### 7.4 Session Management (1 hr)
```python
# conversation/sessions.py
sessions: dict[str, ConversationBuffer] = {}

def get_session(session_id: str) -> ConversationBuffer:
    if session_id not in sessions:
        sessions[session_id] = ConversationBuffer()
    return sessions[session_id]
```

---

## 📊 Phase 3 Metrics Targets

| Metric | Current (Phase 2) | Phase 3 Target |
|--------|------------------|----------------|
| Retrieval method | TF-IDF only | Hybrid (TF-IDF + Vector) |
| Avg latency (CLI) | 0.89s | < 0.5s |
| Avg latency (API) | N/A | < 2s |
| Valid response rate | 100% | > 99.5% |
| Retrieval relevance | 95% | > 98% |
| Faithfulness | 90% | > 97% |
| Knowledge base size | 24 chunks | 100+ chunks |
| Interface | CLI only | CLI + REST API |
| Confidence — high | 7/20 | > 15/20 |
| Test queries | 20 | 50+ |

---

## 🗺️ Recommended Sprint Plan

```
Sprint 1 (Week 1):
  M1 (Vector Search) → The foundation upgrade
  M2 (REST API) → The interface upgrade
  → Both together give you a server with semantic search

Sprint 2 (Week 2):
  M3 (Advanced Retrieval) → Better search quality
  M6 (Knowledge Base) → More coverage
  → More data + better search = dramatically better answers

Sprint 3 (Week 3):
  M4 (Hardening) + M5 (Monitoring)
  → Make it reliable and observable

Sprint 4 (Week 4):
  M7 (Conversations)
  → Multi-turn polish
  → Final testing and documentation
```

---

## 🔄 Relationship with Task 15

```
Task 14 (Static)              Task 15 (Dynamic)
─────────────────              ─────────────────
M1: Vector Search  ──────→  Already has ChromaDB
M2: REST API       ──────→  Already has FastAPI server
M3: Adv Retrieval  ──────→  Partially implemented
M4: Hardening      ──────→  Not yet implemented
M5: Monitoring     ──────→  Not yet implemented
M6: KB Expansion   ──────→  Already has document upload
M7: Conversations  ──────→  Not yet implemented
```

**Strategy:** Build features here first that aren't in Task 15 yet, then port them over.
Prioritize M4 (Hardening) and M5 (Monitoring) since Task 15 doesn't have them yet.

---

## 📁 Suggested File Structure After Phase 3

```
Task 14/
├── api/                          # NEW
│   ├── __init__.py
│   ├── main.py                   # FastAPI server
│   ├── models.py                 # Pydantic schemas
│   └── router.py                 # Route handlers
├── retrieval/                    # NEW
│   ├── __init__.py
│   ├── embeddings.py             # Embedding model wrapper
│   ├── vector_store.py           # ChromaDB wrapper
│   └── hybrid.py                 # Hybrid search + re-ranking
├── conversation/                 # NEW
│   ├── __init__.py
│   ├── history.py                # Conversation buffer
│   └── rephraser.py              # Query rephrasing
├── monitoring/                   # NEW
│   ├── __init__.py
│   ├── tracer.py                 # LangFuse integration
│   ├── metrics.py                # Prometheus metrics
│   └── report.py                 # HTML report generator
├── scripts/                      # NEW
│   ├── manage_kb.py              # KB editor CLI
│   ├── migrate_to_vector.py      # Migration script
│   └── compare_configs.py        # A/B comparison tool
├── knowledge/                    # NEW (JSON chunk files)
│   ├── passwords.json
│   ├── network.json
│   ├── software.json
│   └── ...
├── config.py                     # (extended with profiles)
├── knowledge_base.py             # (kept as fallback)
├── rag_engine.py                 # (extended)
├── guardrails.py                 # (unchanged)
├── cost_tracker.py               # (extended with profiles)
├── evaluator.py                  # (unchanged)
├── test_queries.py               # (expanded to 50+)
├── test_runner.py                # (extended with --host flag)
├── test_results.json
├── phase2_checklist.md
├── PHASE3_ROADMAP.md             # This file
├── requirements.txt              # (extended)
├── Dockerfile                    # NEW
└── docker-compose.yml            # NEW
```

---

## ✅ Quick Wins (Do First)

These items can be done in **under 2 hours** and give immediate value:

1. **Add `.env` loading to `config.py`** — Already done in Task 15, easy port
2. **Expand test queries to 50** — Just add more questions covering edge cases
3. **Add `get_api_key()` lazy loader** — Already done in Task 15, easy port
4. **Save test results with timestamped filenames** — Never overwrite old results
5. **Add answer quality checks to `test_runner.py`** — Flag answers like "I don't know" as warnings

---

*Generated: June 8, 2026 | Task 14 — Static RAG (Phase 2 Complete)*
