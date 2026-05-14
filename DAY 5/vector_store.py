import math
import uuid
from typing import List, Dict, Optional


class VectorStore:
    """
    In-memory vector store.
    Each entry: { id, doc_id, filename, chunk_index, text, embedding }
    """

    def __init__(self):
        self.chunks: List[Dict] = []

    # ── store ──────────────────────────────────────────────────────────────
    def add_chunks(self, chunks: List[Dict]):
        """
        Each chunk must have: doc_id, filename, chunk_index, text, embedding
        Assigns a unique chunkId to each.
        """
        for chunk in chunks:
            chunk["chunkId"] = f"{chunk['doc_id']}_chunk_{chunk['chunk_index']}"
            self.chunks.append(chunk)

    # ── query ──────────────────────────────────────────────────────────────
    def search(self, query_embedding: List[float], top_k: int = 4) -> List[Dict]:
        """Return top-k chunks by cosine similarity."""
        if not self.chunks:
            return []

        scored = []
        for chunk in self.chunks:
            score = self._cosine_similarity(query_embedding, chunk["embedding"])
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored[:top_k]:
            results.append({
                "chunkId":     chunk["chunkId"],
                "doc_id":      chunk["doc_id"],
                "filename":    chunk["filename"],
                "chunk_index": chunk["chunk_index"],
                "text":        chunk["text"],
                "score":       round(score, 4)
            })
        return results

    # ── utils ──────────────────────────────────────────────────────────────
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot   = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def is_empty(self) -> bool:
        return len(self.chunks) == 0

    def get_stats(self) -> Dict:
        if not self.chunks:
            return {"total_chunks": 0, "documents": []}

        docs = {}
        for c in self.chunks:
            fn = c["filename"]
            docs[fn] = docs.get(fn, 0) + 1

        return {
            "total_chunks": len(self.chunks),
            "documents": [
                {"filename": fn, "chunks": count}
                for fn, count in docs.items()
            ]
        }

    def delete_document(self, doc_id: str):
        self.chunks = [c for c in self.chunks if c["doc_id"] != doc_id]
