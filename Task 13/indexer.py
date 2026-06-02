"""
RAG Indexing Pipeline
=====================
Phase 2 – RAG Engineering | Owner: Both

Ingestion flow: Document → Chunking → Embedding → Store (JSON)
Uses Groq API for LLM calls; sentence-transformers for embeddings.

Env vars required:
  GROQ_API_KEY   – your Groq API key
  CHUNK_SIZE     – tokens per chunk          (default: 512)
  CHUNK_OVERLAP  – overlap between chunks    (default: 64)
  INDEX_PATH     – path to the JSON index    (default: data/index.json)
"""

import os
import json
import time
import hashlib
import logging
import textwrap
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Deps: pip install sentence-transformers groq
# ---------------------------------------------------------------------------
from sentence_transformers import SentenceTransformer
from groq import Groq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/indexer.log"),
    ],
)
log = logging.getLogger("rag.indexer")

# ---------------------------------------------------------------------------
# Config (from env with sensible defaults)
# ---------------------------------------------------------------------------
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", 512))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 64))
INDEX_PATH    = Path(os.getenv("INDEX_PATH", "data/index.json"))
EMBED_MODEL   = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_id(text: str) -> str:
    """Stable SHA-256 hash used as a document/chunk identifier."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_index() -> dict:
    """Load existing index from disk, or return an empty structure."""
    if INDEX_PATH.exists():
        with INDEX_PATH.open("r", encoding="utf-8") as f:
            idx = json.load(f)
        log.info("Loaded existing index with %d chunks from %s", len(idx.get("chunks", [])), INDEX_PATH)
        return idx
    log.info("No existing index found – starting fresh.")
    return {"metadata": {"created_at": datetime.now(timezone.utc).isoformat(), "chunks": 0}, "chunks": []}


def save_index(index: dict) -> None:
    """Persist the index to disk as JSON."""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    index["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    index["metadata"]["chunks"] = len(index["chunks"])
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    log.info("Index saved → %s  (%d chunks total)", INDEX_PATH, index["metadata"]["chunks"])


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Naive word-count chunker with overlap.
    For production consider tiktoken for exact token counts.
    """
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    log.debug("Chunked text into %d pieces (size=%d, overlap=%d)", len(chunks), chunk_size, overlap)
    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

_embed_model_cache: Optional[SentenceTransformer] = None

def get_embed_model() -> SentenceTransformer:
    global _embed_model_cache
    if _embed_model_cache is None:
        log.info("Loading embedding model: %s", EMBED_MODEL)
        _embed_model_cache = SentenceTransformer(EMBED_MODEL)
    return _embed_model_cache


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return list-of-list float embeddings for a batch of texts."""
    model = get_embed_model()
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return vectors.tolist()


# ---------------------------------------------------------------------------
# Core indexing
# ---------------------------------------------------------------------------

def index_document(
    text: str,
    source: str = "unknown",
    metadata: Optional[dict] = None,
    reindex: bool = False,
) -> dict:
    """
    Index a single document.

    Parameters
    ----------
    text     : raw document text
    source   : human-readable source label (filename, URL, …)
    metadata : arbitrary key-value pairs stored alongside each chunk
    reindex  : if True, remove existing chunks from this source first

    Returns
    -------
    dict  summary { source, chunks_added, chunks_skipped, duration_s }
    """
    if not GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    t0 = time.perf_counter()
    index = load_index()
    existing_ids = {c["id"] for c in index["chunks"]}

    if reindex:
        before = len(index["chunks"])
        index["chunks"] = [c for c in index["chunks"] if c["source"] != source]
        log.info("Re-index: removed %d old chunks for source '%s'", before - len(index["chunks"]), source)
        existing_ids = {c["id"] for c in index["chunks"]}

    chunks     = chunk_text(text)
    embeddings = embed_texts(chunks)

    added = skipped = 0
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        cid = _doc_id(chunk)
        if cid in existing_ids and not reindex:
            skipped += 1
            continue

        index["chunks"].append({
            "id":         cid,
            "source":     source,
            "chunk_idx":  i,
            "text":       chunk,
            "embedding":  vector,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "metadata":   metadata or {},
        })
        existing_ids.add(cid)
        added += 1

    save_index(index)
    duration = round(time.perf_counter() - t0, 2)
    summary = {
        "source":         source,
        "chunks_added":   added,
        "chunks_skipped": skipped,
        "total_chunks":   len(index["chunks"]),
        "duration_s":     duration,
    }
    log.info("Indexing complete: %s", summary)
    return summary


def index_file(filepath: str, reindex: bool = False) -> dict:
    """Convenience wrapper: read a .txt/.md file and index it."""
    p = Path(filepath)
    text = p.read_text(encoding="utf-8")
    return index_document(text, source=str(p), metadata={"filename": p.name}, reindex=reindex)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Indexer – ingest documents into JSON vector store")
    parser.add_argument("files", nargs="+", help="Text/Markdown files to index")
    parser.add_argument("--reindex", action="store_true", help="Drop existing chunks for these sources and re-index")
    args = parser.parse_args()

    results = []
    for f in args.files:
        log.info("Indexing file: %s", f)
        result = index_file(f, reindex=args.reindex)
        results.append(result)

    # Write run summary
    summary_path = Path("data/last_index_run.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w") as sf:
        json.dump({"run_at": datetime.now(timezone.utc).isoformat(), "results": results}, sf, indent=2)

    print(f"\n✅  Indexed {len(results)} file(s). Summary → {summary_path}")
    for r in results:
        print(f"   {r['source']}: +{r['chunks_added']} chunks added, {r['chunks_skipped']} skipped ({r['duration_s']}s)")
