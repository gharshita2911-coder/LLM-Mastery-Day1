from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import json
import uuid
import re
from typing import List, Dict
from vector_store import VectorStore
from token_logger import log_token_usage

load_dotenv()

COST_PER_INPUT_TOKEN  = 0.10 / 1_000_000
COST_PER_OUTPUT_TOKEN = 0.40 / 1_000_000

CHUNK_SIZE     = 400
CHUNK_OVERLAP  = 80
TOP_K          = 4
MIN_SIMILARITY = 0.45

EMBED_MODEL    = "models/gemini-embedding-001"
GENERATE_MODEL = "gemini-2.5-flash-lite"


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
            raise Exception("No Gemini API keys found. Set GEMINI_API_KEY_1 in .env")

        self.vector_store = VectorStore()
        # Build clients for each key
        self.clients = [genai.Client(api_key=key) for key in self.api_keys]

    # ══════════════════════════════════════════════════════════════════════
    #  INGEST
    # ══════════════════════════════════════════════════════════════════════

    def ingest_document(self, file_bytes: bytes, filename: str) -> Dict:
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            text = self._clean_text(text)

            if len(text.strip()) < 20:
                return {"error": "Document is empty or too short"}

            chunks_text = self._chunk_text(text)
            print(f"\n[INGEST] {filename}: {len(chunks_text)} chunks to embed...")

            doc_id = str(uuid.uuid4())[:8]
            chunks_to_store = []

            for i, chunk_text in enumerate(chunks_text):
                print(f"  Embedding chunk {i+1}/{len(chunks_text)}...")
                embedding = self._embed(chunk_text)
                chunks_to_store.append({
                    "doc_id":      doc_id,
                    "filename":    filename,
                    "chunk_index": i,
                    "text":        chunk_text,
                    "embedding":   embedding
                })

            self.vector_store.add_chunks(chunks_to_store)
            print(f"[INGEST] Done. {len(chunks_to_store)} chunks stored.")

            return {
                "success":       True,
                "doc_id":        doc_id,
                "filename":      filename,
                "chunks_stored": len(chunks_to_store),
                "total_chars":   len(text)
            }

        except Exception as e:
            print(f"[INGEST ERROR] {e}")
            return {"error": f"Ingestion failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════════════════
    #  ASK
    # ══════════════════════════════════════════════════════════════════════

    def answer_question(self, question: str) -> Dict:
        try:
            query_embedding = self._embed(question)
            retrieved       = self.vector_store.search(query_embedding, top_k=TOP_K)

            print(f"\n[SEARCH] Top scores: {[r['score'] for r in retrieved]}")

            if not retrieved or retrieved[0]["score"] < MIN_SIMILARITY:
                print(f"[SEARCH] Below threshold {MIN_SIMILARITY} — returning cannot-find")
                return {
                    "answer":   "I cannot find relevant information in the uploaded documents to answer this question.",
                    "sources":  [],
                    "tokens":   None,
                    "cost_usd": 0.0
                }

            context_parts = []
            for r in retrieved:
                context_parts.append(
                    f"[SOURCE: {r['filename']} | chunk {r['chunk_index']} | id: {r['chunkId']}]\n{r['text']}"
                )
            context = "\n\n---\n\n".join(context_parts)

            prompt = f"""You are a precise knowledge base assistant. Answer the user's question using ONLY the context provided below.

Rules:
- Answer strictly from the context. Do NOT use outside knowledge.
- If the answer is not present in the context, say exactly: "I cannot find relevant information in the uploaded documents to answer this question."
- Be concise and accurate.
- Return ONLY valid JSON with no markdown, no backticks, no extra text.

JSON schema:
{{
    "answer": "<your answer>",
    "sources": [
        {{
            "chunkId": "<id from context header>",
            "snippet": "<short exact phrase from that chunk, max 30 words>"
        }}
    ]
}}

If the answer is not found, return sources as [].

CONTEXT:
{context}

QUESTION:
{question}
"""

            response, usage = self._generate(prompt)

            prompt_tokens     = usage.prompt_token_count
            completion_tokens = usage.candidates_token_count
            cost_usd          = self._calc_cost(prompt_tokens, completion_tokens)

            log_token_usage(usage)

            raw = response.replace("```json", "").replace("```", "").strip()
            print(f"\n[GEMINI RAW]\n{raw}\n")

            result = json.loads(raw)
            self._validate_answer(result, retrieved)

            result["tokens"] = {
                "prompt":     prompt_tokens,
                "completion": completion_tokens,
                "total":      prompt_tokens + completion_tokens
            }
            result["cost_usd"] = cost_usd

            return result

        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Gemini JSON: {str(e)}"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _chunk_text(self, text: str) -> List[str]:
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
        for client in self.clients:
            try:
                result = client.models.embed_content(
                    model=EMBED_MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                return result.embeddings[0].values
            except Exception as e:
                last_error = str(e)
                print(f"  [EMBED] client failed: {e}")
                continue
        raise Exception(f"All embedding clients failed: {last_error}")

    def _generate(self, prompt: str):
        last_error = None
        for client in self.clients:
            try:
                response = client.models.generate_content(
                    model=GENERATE_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0
                    )
                )
                return response.text, response.usage_metadata
            except Exception as e:
                last_error = str(e)
                print(f"  [GEN] client failed: {e}")
                continue
        raise Exception(f"All generation clients failed: {last_error}")

    def _validate_answer(self, result: Dict, retrieved: List[Dict]):
        required = {"answer", "sources"}
        missing  = required - set(result.keys())
        if missing:
            raise ValueError(f"Missing fields: {missing}")

        valid_ids = {r["chunkId"] for r in retrieved}
        cleaned   = []
        for source in result.get("sources", []):
            if "chunkId" not in source or "snippet" not in source:
                continue
            if source["chunkId"] in valid_ids:
                cleaned.append(source)
        result["sources"] = cleaned

    def _calc_cost(self, pt: int, ct: int) -> float:
        return round(pt * COST_PER_INPUT_TOKEN + ct * COST_PER_OUTPUT_TOKEN, 8)