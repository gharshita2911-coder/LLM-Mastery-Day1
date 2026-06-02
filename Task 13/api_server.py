"""
RAG REST API Server
===================
FastAPI server — test every RAG operation via Thunder Client, Postman, or Hoppscotch.

Install extras:
  pip install fastapi uvicorn python-multipart

Run:
  uvicorn src.api_server:app --reload --port 8000

Base URL: http://localhost:8000
Docs UI:  http://localhost:8000/docs      ← interactive Swagger UI
"""

import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query as QParam
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── make src/ importable when running as `uvicorn src.api_server:app` ─
sys.path.insert(0, str(Path(__file__).parent))

from query        import query as rag_query, load_index
from indexer      import index_document, index_file
from batch_runner import run_batch, load_stored_queries, BATCH_RESULTS_PATH, STORED_QUERIES_PATH

# ── logging ───────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/api_server.log"),
    ],
)
log = logging.getLogger("rag.api")

# ── app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="RAG API",
    description="Retrieval-Augmented Generation — index documents, run queries, manage stored queries",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════
# Pydantic models
# ══════════════════════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    question: str = Field(..., example="What is the refund policy?")
    top_k: int    = Field(5, ge=1, le=20, example=5)
    save: bool    = Field(True, description="Append result to query_results.json")

class IndexTextRequest(BaseModel):
    text:   str            = Field(..., example="Refunds are processed within 5-7 business days.")
    source: str            = Field("api-upload", example="manual-entry")
    metadata: dict         = Field(default_factory=dict)
    reindex: bool          = Field(False)

class StoredQueryCreate(BaseModel):
    id:       str        = Field(..., example="q010")
    question: str        = Field(..., example="How do I reset my password?")
    top_k:    int        = Field(5, ge=1, le=20)
    tags:     list[str]  = Field(default_factory=list)
    enabled:  bool       = Field(True)

class BatchRunRequest(BaseModel):
    ids:              Optional[list[str]] = Field(None, example=["q001", "q002"])
    tags:             Optional[list[str]] = Field(None, example=["policy"])
    include_disabled: bool                = Field(False)


# ══════════════════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
def root():
    """Health check — confirm the server is running."""
    return {
        "status":    "ok",
        "service":   "RAG API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "docs":      "/docs",
    }

@app.get("/health", tags=["Health"])
def health():
    """Detailed health: index stats + stored query count."""
    try:
        idx    = load_index()
        chunks = len(idx.get("chunks", []))
        meta   = idx.get("metadata", {})
    except Exception:
        chunks, meta = 0, {}

    try:
        stored = load_stored_queries()
        sq_count = len(stored)
    except Exception:
        sq_count = 0

    return {
        "status":          "ok",
        "index_chunks":    chunks,
        "index_updated_at": meta.get("updated_at"),
        "stored_queries":  sq_count,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Query endpoints
# ══════════════════════════════════════════════════════════════════════

@app.post("/query", tags=["Query"])
def run_query(req: QueryRequest):
    """
    Ask a question against the indexed documents.

    - Embeds question → cosine similarity search → Groq LLM → answer
    - Result saved to `data/query_results.json` when `save=true`
    """
    log.info("POST /query — %s", req.question)
    try:
        result = rag_query(req.question, top_k=req.top_k, save=req.save)
        return {"status": "ok", "data": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.error("Query error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query/results", tags=["Query"])
def get_query_results(limit: int = QParam(20, ge=1, le=200)):
    """Return the last N query results from `data/query_results.json`."""
    results_path = Path("data/query_results.json")
    if not results_path.exists():
        return {"status": "ok", "data": [], "total": 0}
    with results_path.open() as f:
        all_results = json.load(f)
    return {
        "status": "ok",
        "total":  len(all_results),
        "data":   all_results[-limit:],
    }


# ══════════════════════════════════════════════════════════════════════
# Stored queries CRUD
# ══════════════════════════════════════════════════════════════════════

def _save_stored_queries(queries: list[dict]) -> None:
    STORED_QUERIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STORED_QUERIES_PATH.open("w", encoding="utf-8") as f:
        json.dump(queries, f, indent=2, ensure_ascii=False)


@app.get("/stored-queries", tags=["Stored Queries"])
def list_stored_queries(
    tag:     Optional[str] = QParam(None, description="Filter by tag"),
    enabled: Optional[bool] = QParam(None, description="Filter by enabled status"),
):
    """List all stored queries (with optional filters)."""
    try:
        queries = load_stored_queries()
    except FileNotFoundError:
        return {"status": "ok", "data": [], "total": 0}

    if tag is not None:
        queries = [q for q in queries if tag in q.get("tags", [])]
    if enabled is not None:
        queries = [q for q in queries if q.get("enabled", True) == enabled]

    return {"status": "ok", "total": len(queries), "data": queries}


@app.post("/stored-queries", tags=["Stored Queries"], status_code=201)
def create_stored_query(req: StoredQueryCreate):
    """Add a new stored query."""
    try:
        queries = load_stored_queries()
    except FileNotFoundError:
        queries = []

    if any(q["id"] == req.id for q in queries):
        raise HTTPException(status_code=409, detail=f"Query ID '{req.id}' already exists.")

    new_q = req.model_dump()
    queries.append(new_q)
    _save_stored_queries(queries)
    log.info("Stored query created: %s", req.id)
    return {"status": "created", "data": new_q}


@app.get("/stored-queries/{query_id}", tags=["Stored Queries"])
def get_stored_query(query_id: str):
    """Get a single stored query by ID."""
    queries = load_stored_queries()
    match = next((q for q in queries if q["id"] == query_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")
    return {"status": "ok", "data": match}


@app.patch("/stored-queries/{query_id}", tags=["Stored Queries"])
def update_stored_query(query_id: str, updates: dict):
    """
    Partially update a stored query.

    Send only the fields you want to change:
    `{ "enabled": false }` or `{ "top_k": 8, "tags": ["billing"] }`
    """
    queries = load_stored_queries()
    for q in queries:
        if q["id"] == query_id:
            q.update({k: v for k, v in updates.items() if k != "id"})
            _save_stored_queries(queries)
            log.info("Stored query updated: %s", query_id)
            return {"status": "updated", "data": q}
    raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")


@app.delete("/stored-queries/{query_id}", tags=["Stored Queries"])
def delete_stored_query(query_id: str):
    """Delete a stored query by ID."""
    queries = load_stored_queries()
    new_list = [q for q in queries if q["id"] != query_id]
    if len(new_list) == len(queries):
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found.")
    _save_stored_queries(new_list)
    log.info("Stored query deleted: %s", query_id)
    return {"status": "deleted", "id": query_id}


# ══════════════════════════════════════════════════════════════════════
# Batch execution
# ══════════════════════════════════════════════════════════════════════

@app.post("/batch/run", tags=["Batch"])
def run_batch_endpoint(req: BatchRunRequest = BatchRunRequest()):
    """
    Execute stored queries in batch.

    - Omit `ids` and `tags` to run all enabled queries
    - Filter by `ids`: `["q001","q003"]`
    - Filter by `tags`: `["policy","billing"]`
    - Set `include_disabled: true` to include disabled queries too
    """
    log.info("POST /batch/run — ids=%s tags=%s", req.ids, req.tags)
    try:
        report = run_batch(
            ids=req.ids,
            tags=req.tags,
            include_disabled=req.include_disabled,
        )
        return {"status": "ok", "data": report}
    except Exception as e:
        log.error("Batch run error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch/results", tags=["Batch"])
def get_batch_results(limit: int = QParam(10, ge=1, le=100)):
    """Return the last N batch run reports from `data/batch_results.json`."""
    if not BATCH_RESULTS_PATH.exists():
        return {"status": "ok", "data": [], "total": 0}
    with BATCH_RESULTS_PATH.open() as f:
        history = json.load(f)
    return {
        "status": "ok",
        "total":  len(history),
        "data":   history[-limit:],
    }


# ══════════════════════════════════════════════════════════════════════
# Indexing endpoints
# ══════════════════════════════════════════════════════════════════════

@app.post("/index/text", tags=["Index"])
def index_text(req: IndexTextRequest):
    """Index raw text directly (no file upload needed)."""
    log.info("POST /index/text — source=%s", req.source)
    try:
        result = index_document(
            text=req.text,
            source=req.source,
            metadata=req.metadata,
            reindex=req.reindex,
        )
        return {"status": "ok", "data": result}
    except Exception as e:
        log.error("Index text error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/file", tags=["Index"])
async def index_file_endpoint(
    file: UploadFile = File(...),
    reindex: bool = QParam(False),
):
    """Upload a .txt or .md file and index it."""
    log.info("POST /index/file — %s", file.filename)
    try:
        content = await file.read()
        text = content.decode("utf-8")
        result = index_document(
            text=text,
            source=file.filename or "uploaded-file",
            metadata={"original_filename": file.filename},
            reindex=reindex,
        )
        return {"status": "ok", "data": result}
    except Exception as e:
        log.error("Index file error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/index/stats", tags=["Index"])
def index_stats():
    """Return index metadata and per-source chunk counts."""
    try:
        idx = load_index()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No index found. Run indexer.py first.")

    chunks = idx.get("chunks", [])
    sources: dict[str, int] = {}
    for c in chunks:
        sources[c["source"]] = sources.get(c["source"], 0) + 1

    return {
        "status":   "ok",
        "metadata": idx.get("metadata", {}),
        "total_chunks": len(chunks),
        "sources":  sources,
    }
