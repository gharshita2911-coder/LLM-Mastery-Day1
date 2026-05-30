"""
rag_engine.py
=============
Responsibilities:
  1. Ingest documents — plain text, .txt, .md, .pdf, .docx (file upload support)
  2. Chunk documents into overlapping passages
  3. Embed all chunks using TF-IDF (local, no API key)
  4. Store L2-normalised vectors in an in-memory NumPy matrix
  5. Cosine search: return top-k chunks for a query

Public API:
  engine = RAGEngine()
  engine.add_document(text, title, doc_id)          # from raw string
  engine.ingest_file(path)                           # from file (txt/md/pdf/docx)
  engine.build()                                     # fit TF-IDF and build matrix
  chunks = engine.search(query, k=3)                 # returns list[dict]
  engine.stats()                                     # index health info
"""

import os
import re
import uuid
import hashlib
from pathlib import Path
from typing import Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


# ── optional parsers (gracefully absent) ────────────────────────────────────
try:
    import PyPDF2
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

try:
    from docx import Document as DocxDocument
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 200   # words per chunk
CHUNK_OVERLAP = 40    # words of overlap between consecutive chunks
MAX_FEATURES  = 10_000
SUPPORTED_EXT = {".txt", ".md", ".pdf", ".docx"}


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_pdf(path: str) -> str:
    if not _PDF_OK:
        raise ImportError("PyPDF2 not installed. Run: pip install PyPDF2")
    text_parts = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def _extract_docx(path: str) -> str:
    if not _DOCX_OK:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(path: str) -> str:
    """Extract plain text from .txt / .md / .pdf / .docx files."""
    ext = Path(path).suffix.lower()
    if ext in (".txt", ".md"):
        return _extract_txt(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    raise ValueError(
        f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXT))}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    doc_id: str,
    title: str,
    chunk_size: int  = CHUNK_SIZE,
    overlap: int     = CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split text into overlapping word-boundary chunks.
    Returns list of chunk dicts: {id, doc_id, title, text, chunk_index}.
    """
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()

    if not words:
        return []

    chunks = []
    step   = max(1, chunk_size - overlap)

    for i, start in enumerate(range(0, len(words), step)):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            break
        chunk_text_str = " ".join(chunk_words)
        chunk_id = f"{doc_id}_c{i}"
        chunks.append({
            "id":          chunk_id,
            "doc_id":      doc_id,
            "title":       title,
            "text":        chunk_text_str,
            "chunk_index": i,
            "word_count":  len(chunk_words),
        })
        # Stop if we've consumed all words
        if start + chunk_size >= len(words):
            break

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# RAGEngine
# ─────────────────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    Manages the full lifecycle:
      add docs → chunk → build TF-IDF index → search
    """

    def __init__(
        self,
        chunk_size:   int = CHUNK_SIZE,
        overlap:      int = CHUNK_OVERLAP,
        max_features: int = MAX_FEATURES,
        top_k:        int = 3,
    ):
        self.chunk_size   = chunk_size
        self.overlap      = overlap
        self.max_features = max_features
        self.top_k        = top_k

        # Raw documents before chunking
        self._raw_docs: list[dict] = []       # [{id, title, text, source}]

        # Index state (populated by build())
        self.chunks:      list[dict]              = []
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matrix:     Optional[np.ndarray]      = None
        self._built       = False

    # ── Document ingestion ────────────────────────────────────────────────

    def add_document(
        self,
        text:   str,
        title:  str,
        doc_id: Optional[str] = None,
        source: str = "manual",
    ) -> str:
        """Add a raw text document. Returns the doc_id assigned."""
        if not text.strip():
            raise ValueError("Document text cannot be empty.")
        if doc_id is None:
            # Deterministic ID from content hash for deduplication
            doc_id = "doc_" + hashlib.md5(text.encode()).hexdigest()[:8]

        # Deduplicate by doc_id
        existing_ids = {d["id"] for d in self._raw_docs}
        if doc_id in existing_ids:
            print(f"  ⚠  Document '{doc_id}' already exists — skipping.")
            return doc_id

        self._raw_docs.append({
            "id":     doc_id,
            "title":  title,
            "text":   text,
            "source": source,
        })
        self._built = False   # index is now stale
        return doc_id

    def ingest_file(self, path: str, title: Optional[str] = None) -> str:
        """
        Extract text from a file and add it to the engine.
        Supports: .txt, .md, .pdf, .docx
        Returns the doc_id assigned.
        """
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_EXT:
            raise ValueError(
                f"Unsupported extension '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXT))}"
            )

        print(f"  📄  Ingesting: {path}")
        text = extract_text(path)

        if not text.strip():
            raise ValueError(f"No text could be extracted from: {path}")

        if title is None:
            title = Path(path).stem.replace("_", " ").replace("-", " ").title()

        # Use a stable doc_id derived from the filename
        doc_id = "file_" + hashlib.md5(path.encode()).hexdigest()[:8]
        return self.add_document(text, title, doc_id=doc_id, source=path)

    def ingest_directory(self, directory: str) -> list[str]:
        """
        Recursively ingest all supported files in a directory.
        Returns list of doc_ids.
        """
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"Not a directory: {directory}")

        doc_ids = []
        for root, _, files in os.walk(directory):
            for fname in sorted(files):
                ext = Path(fname).suffix.lower()
                if ext in SUPPORTED_EXT:
                    full_path = os.path.join(root, fname)
                    try:
                        doc_id = self.ingest_file(full_path)
                        doc_ids.append(doc_id)
                    except Exception as e:
                        print(f"  ⚠  Skipped {fname}: {e}")
        return doc_ids

    # ── Index building ────────────────────────────────────────────────────

    def build(self) -> "RAGEngine":
        """
        Chunk all raw documents and fit the TF-IDF index.
        Must be called before search(). Safe to call multiple times (rebuilds).
        """
        if not self._raw_docs:
            raise RuntimeError(
                "No documents loaded. Call add_document() or ingest_file() first."
            )

        print(f"\n🔧  Building index over {len(self._raw_docs)} document(s)...")

        # Chunk every document
        all_chunks: list[dict] = []
        for doc in self._raw_docs:
            doc_chunks = chunk_text(
                doc["text"], doc["id"], doc["title"],
                self.chunk_size, self.overlap,
            )
            all_chunks.extend(doc_chunks)
            print(f"     {doc['id']:20s}  →  {len(doc_chunks)} chunks  ({doc['title'][:40]})")

        if not all_chunks:
            raise RuntimeError("All documents produced zero chunks.")

        # Fit TF-IDF on chunk texts
        texts = [c["text"] for c in all_chunks]
        self._vectorizer = TfidfVectorizer(
            ngram_range  = (1, 2),
            max_features = self.max_features,
            sublinear_tf = True,
            stop_words   = "english",
        )
        raw_matrix   = self._vectorizer.fit_transform(texts).toarray().astype("float32")
        self._matrix = normalize(raw_matrix, norm="l2")   # each row = unit vector

        self.chunks = all_chunks
        self._built = True

        print(f"✅  Index ready — {len(self.chunks)} chunks, vocab={self._matrix.shape[1]:,}\n")
        return self

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str, k: Optional[int] = None) -> list[dict]:
        """
        Embed query with the fitted vectorizer and return top-k chunks
        sorted by cosine similarity (descending).

        Returns list of dicts: {id, doc_id, title, text, chunk_index, score}
        """
        if not self._built or self._matrix is None or self._vectorizer is None:
            raise RuntimeError("Index not built. Call build() first.")

        k = k or self.top_k
        raw_q = self._vectorizer.transform([query]).toarray().astype("float32")
        q_vec = normalize(raw_q, norm="l2")[0]
        scores   = self._matrix @ q_vec
        top_idx  = np.argsort(scores)[::-1][:k]
        return [{**self.chunks[i], "score": round(float(scores[i]), 4)} for i in top_idx]

    # ── Utilities ─────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return index health statistics."""
        return {
            "documents":       len(self._raw_docs),
            "chunks":          len(self.chunks),
            "built":           self._built,
            "vocab_size":      int(self._matrix.shape[1]) if self._matrix is not None else 0,
            "chunk_size":      self.chunk_size,
            "overlap":         self.overlap,
            "doc_titles":      [d["title"] for d in self._raw_docs],
        }

    def list_documents(self) -> list[dict]:
        """List all loaded documents (not chunks)."""
        return [
            {"id": d["id"], "title": d["title"], "source": d["source"],
             "chars": len(d["text"])}
            for d in self._raw_docs
        ]

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document by ID and mark index as stale. Returns True if found."""
        before = len(self._raw_docs)
        self._raw_docs = [d for d in self._raw_docs if d["id"] != doc_id]
        if len(self._raw_docs) < before:
            self._built = False
            self.chunks = []
            self._matrix = None
            self._vectorizer = None
            return True
        return False
