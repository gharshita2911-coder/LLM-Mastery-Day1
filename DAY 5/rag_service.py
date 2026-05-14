import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import uuid
import re
from typing import List, Dict
from vector_store import VectorStore
from token_logger import log_token_usage

load_dotenv()

# ── Gemini pricing for gemini-2.5-flash-lite ──────────────────────────────
COST_PER_INPUT_TOKEN  = 0.10 / 1_000_000
COST_PER_OUTPUT_TOKEN = 0.40 / 1_000_000

# ── Chunking config ───────────────────────────────────────────────────────
CHUNK_SIZE    = 400   # characters per chunk
CHUNK_OVERLAP = 80    # overlap between consecutive chunks
TOP_K         = 4     # chunks retrieved per query

# ── Similarity threshold — below this we consider "not in context" ────────
MIN_SIMILARITY = 0.45


class RAGService:

    def __init__(self):
        self.api_keys = [
            key for key in [
                os.getenv("GEMINI_API_KEY_1"),
                os.getenv("GEMINI_API_KEY_2"),
                os.getenv("GEMINI_API_KEY_3"),
                os.getenv("GEMINI_API_KEY_4"),
            ]
            if key
        ]
        if not self.api_keys:
            raise Exception("No valid Gemini API keys found")

        self.model_name     = "gemini-2.5-flash-lite"
        self.embed_model    = "models/text-embedding-004"
        self.vector_store   = VectorStore()

    # ══════════════════════════════════════════════════════════════════════
    #  INGEST
    # ══════════════════════════════════════════════════════════════════════

    def ingest_document(self, file_bytes: bytes, filename: str) -> Dict:
        """Chunk → embed → store. Returns ingestion summary."""
        try:
            # 1. Decode text
            text = file_bytes.decode("utf-8", errors="replace")
            text = self._clean_text(text)

            if len(text.strip()) < 20:
                return {"error": "Document appears empty or too short"}

            # 2. Chunk
            chunks_text = self._chunk_text(text)
            print(f"\n[INGEST] {filename}: {len(chunks_text)} chunks")

            # 3. Embed all chunks
            doc_id = str(uuid.uuid4())[:8]
            chunks_to_store = []

            for i, chunk_text in enumerate(chunks_text):
                embedding = self._embed(chunk_text)
                chunks_to_store.append({
                    "doc_id":      doc_id,
                    "filename":    filename,
                    "chunk_index": i,
                    "text":        chunk_text,
                    "embedding":   embedding
                })

            # 4. Store
            self.vector_store.add_chunks(chunks_to_store)

            return {
                "success":       True,
                "doc_id":        doc_id,
                "filename":      filename,
                "chunks_stored": len(chunks_to_store),
                "total_chars":   len(text)
            }

        except Exception as e:
            return {"error": f"Ingestion failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════════════════
    #  ASK
    # ══════════════════════════════════════════════════════════════════════

    def answer_question(self, question: str) -> Dict:
        """Embed question → retrieve chunks → generate grounded answer."""
        try:
            # 1. Embed question
            query_embedding = self._embed(question)

            # 2. Retrieve top-k
            retrieved = self.vector_store.search(query_embedding, top_k=TOP_K)

            # 3. Check if best match is above threshold
            if not retrieved or retrieved[0]["score"] < MIN_SIMILARITY:
                return {
                    "answer": "I cannot find relevant information in the uploaded documents to answer this question.",
                    "sources": [],
                    "tokens": None,
                    "cost_usd": 0.0
                }

            # 4. Build context string
            context_parts = []
            for r in retrieved:
                context_parts.append(
                    f"[SOURCE: {r['filename']} | chunk {r['chunk_index']} | id: {r['chunkId']}]\n{r['text']}"
                )
            context = "\n\n---\n\n".join(context_parts)

            # 5. Build prompt
            prompt = f"""You are a precise knowledge base assistant. Answer the user's question using ONLY the context provided below.

Rules:
- Answer strictly from the context. Do NOT use outside knowledge.
- If the answer is not present in the context, reply exactly: "I cannot find relevant information in the uploaded documents to answer this question."
- Be concise and accurate.
- Return ONLY valid JSON — no markdown, no backticks, no preamble.

JSON schema:
{{
    "answer": "<your answer or the cannot-find message>",
    "sources": [
        {{
            "chunkId": "<id from context>",
            "snippet": "<exact short phrase from that chunk supporting the answer, max 30 words>"
        }}
    ]
}}

If the answer is not found, return sources as an empty array [].

CONTEXT:
{context}

QUESTION:
{question}
"""

            # 6. Generate
            response = self._generate(prompt)
            usage    = response.usage_metadata
            log_token_usage(usage)

            prompt_tokens     = usage.prompt_token_count
            completion_tokens = usage.candidates_token_count
            cost_usd          = self._calc_cost(prompt_tokens, completion_tokens)

            # 7. Parse
            raw = response.text.replace("```json", "").replace("```", "").strip()
            print("\n[GEMINI RESPONSE]\n", raw)

            result = json.loads(raw)
            self._validate_answer(result, retrieved)

            result["tokens"] = {
                "prompt":     prompt_tokens,
                "completion": completion_tokens,
                "total":      usage.total_token_count
            }
            result["cost_usd"] = cost_usd

            return result

        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse JSON response: {str(e)}"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _clean_text(self, text: str) -> str:
        # Normalize whitespace; keep newlines for context
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _chunk_text(self, text: str) -> List[str]:
        """Sliding-window character-level chunking with overlap."""
        chunks = []
        start  = 0
        length = len(text)

        while start < length:
            end   = min(start + CHUNK_SIZE, length)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == length:
                break
            start += CHUNK_SIZE - CHUNK_OVERLAP

        return chunks

    def _embed(self, text: str) -> List[float]:
        last_error = None
        for key in self.api_keys:
            try:
                genai.configure(api_key=key)
                result = genai.embed_content(
                    model=self.embed_model,
                    content=text,
                    task_type="retrieval_document"
                )
                return result["embedding"]
            except Exception as e:
                last_error = str(e)
                continue
        raise Exception(f"All embedding API keys failed: {last_error}")

    def _generate(self, prompt: str):
        last_error = None
        for key in self.api_keys:
            try:
                genai.configure(api_key=key)
                model    = genai.GenerativeModel(self.model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0}
                )
                return response
            except Exception as e:
                last_error = str(e)
                print(f"API key failed: {e}")
                continue
        raise Exception(f"All generation API keys failed: {last_error}")

    def _validate_answer(self, result: Dict, retrieved: List[Dict]):
        """Ensure result has required fields and cited chunks exist in retrieved set."""
        required = {"answer", "sources"}
        missing  = required - set(result.keys())
        if missing:
            raise ValueError(f"Missing fields in response: {missing}")

        valid_ids = {r["chunkId"] for r in retrieved}
        for source in result.get("sources", []):
            if "chunkId" not in source or "snippet" not in source:
                raise ValueError("Each source must have chunkId and snippet")
            if source["chunkId"] not in valid_ids:
                # Hallucinated chunk ID — remove silently rather than crash
                result["sources"] = [
                    s for s in result["sources"]
                    if s.get("chunkId") in valid_ids
                ]
                break

    def _calc_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        cost = (
            prompt_tokens     * COST_PER_INPUT_TOKEN +
            completion_tokens * COST_PER_OUTPUT_TOKEN
        )
        return round(cost, 8)
