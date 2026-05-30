"""
llm_client.py
=============
Single responsibility: talk to Groq.

  build_messages()   — assemble the system + user message from retrieved chunks
  run()              — one full RAG turn: retrieve → prompt → LLM loop → answer
  LLMClient          — thin wrapper around groq.Groq with configurable model/params
"""

from __future__ import annotations
import json
import os
from typing import Optional

from groq import Groq

from rag_engine import RAGEngine
from tools import get_tool_schemas, execute_tool

# ─────────────────────────────────────────────────────────────────────────────
# Defaults (overridable via env vars or LLMClient constructor)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_MODEL          = os.getenv("RAG_MODEL",            "llama-3.3-70b-versatile")
DEFAULT_MAX_TOKENS     = int(os.getenv("RAG_MAX_TOKENS",   "1024"))
DEFAULT_TEMPERATURE    = float(os.getenv("RAG_TEMPERATURE","0.2"))
DEFAULT_TOP_K          = int(os.getenv("RAG_TOP_K",        "3"))
DEFAULT_MAX_TOOL_ROUNDS= int(os.getenv("RAG_MAX_TOOL_ROUNDS","3"))

SYSTEM_PROMPT = (
    "You are a knowledgeable AI assistant with access to a private knowledge base. "
    "Always read the provided context chunks carefully before deciding what to do.\n\n"
    "TOOL USE RULES — follow these strictly:\n"
    "1. If the retrieved context chunks already contain the information needed to answer "
    "the question — including formulas, definitions, comparisons, or explanations — "
    "answer DIRECTLY from the context WITHOUT calling any tool.\n"
    "2. Only call a tool when the context is genuinely missing facts that are required "
    "to answer the question (e.g. live pricing, benchmark numbers, installation steps "
    "not present in any chunk).\n"
    "3. NEVER call 'summarise_document' merely to look up a document you already have "
    "in the context. That tool is only for when you need an overview of a document "
    "whose content was NOT retrieved.\n"
    "4. NEVER call any tool as a confirmation step after the context already provides "
    "the answer.\n\n"
    "Ground every claim in either the retrieved chunks or a tool result."
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a numbered context block for the prompt."""
    if not chunks:
        return "(no relevant context retrieved)"
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[Chunk {i} | doc={c.get('doc_id','?')} | {c['title']} | score={c['score']:.3f}]\n"
            f"{c['text']}"
        )
    return "\n\n".join(parts)


def build_messages(context: str, question: str) -> list[dict]:
    """Return the initial [system, user] message list for a new query."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Context from knowledge base:\n\n{context}\n\n"
                f"---\nQuestion: {question}"
            ),
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# LLMClient
# ─────────────────────────────────────────────────────────────────────────────

class LLMClient:
    """
    Wraps a groq.Groq instance and orchestrates:
      1. Retrieval   (delegates to RAGEngine)
      2. Prompt build
      3. LLM call + tool-call loop
      4. Returns a structured trace dict
    """

    def __init__(
        self,
        api_key:         Optional[str] = None,
        model:           str  = DEFAULT_MODEL,
        max_tokens:      int  = DEFAULT_MAX_TOKENS,
        temperature:     float= DEFAULT_TEMPERATURE,
        top_k:           int  = DEFAULT_TOP_K,
        max_tool_rounds: int  = DEFAULT_MAX_TOOL_ROUNDS,
    ):
        key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Export it or pass api_key= to LLMClient()."
            )
        self._client         = Groq(api_key=key)
        self.model           = model
        self.max_tokens      = max_tokens
        self.temperature     = temperature
        self.top_k           = top_k
        self.max_tool_rounds = max_tool_rounds

    # ── Core method ───────────────────────────────────────────────────────

    def run(
        self,
        engine:   RAGEngine,
        question: str,
        verbose:  bool = False,
    ) -> dict:
        """
        Full RAG + optional tool-call pipeline for one question.

        Returns
        -------
        dict with keys:
          question          str
          retrieved_chunks  list[{title, doc_id, score}]
          tool_calls        list[{round, tool, args, result_preview}]
          final_answer      str
          error             str | None
          llm_calls         int   (number of Groq API calls made)
        """
        trace: dict = {
            "question":         question,
            "retrieved_chunks": [],
            "tool_calls":       [],
            "final_answer":     "",
            "error":            None,
            "llm_calls":        0,
        }

        # ── Step 1: Retrieve ─────────────────────────────────────────────
        try:
            chunks = engine.search(question, k=self.top_k)
        except RuntimeError as e:
            trace["error"] = str(e)
            return trace

        trace["retrieved_chunks"] = [
            {
                "title":  c["title"],
                "doc_id": c.get("doc_id", ""),
                "score":  c["score"],
            }
            for c in chunks
        ]
        context = _format_context(chunks)

        if verbose:
            print(f"\n{'='*62}")
            print(f"Q: {question}")
            print(f"Retrieved {len(chunks)} chunk(s):")
            for c in chunks:
                print(f"  [{c['score']:.3f}]  {c['title']}  (doc={c.get('doc_id','?')})")

        # ── Step 2: Initial prompt ───────────────────────────────────────
        messages = build_messages(context, question)
        tools    = get_tool_schemas()

        # ── Step 3: LLM turn loop ────────────────────────────────────────
        for round_num in range(self.max_tool_rounds + 1):
            try:
                response = self._client.chat.completions.create(
                    model       = self.model,
                    messages    = messages,
                    tools       = tools,
                    tool_choice = "auto",
                    temperature = self.temperature,
                    max_tokens  = self.max_tokens,
                )
            except Exception as e:
                trace["error"] = f"Groq API error (round {round_num}): {e}"
                return trace

            trace["llm_calls"] += 1
            msg = response.choices[0].message

            # No tool calls → this is the final answer
            if not msg.tool_calls:
                trace["final_answer"] = (msg.content or "").strip()
                if verbose:
                    print(f"\nAnswer:\n{trace['final_answer']}")
                break

            # Append assistant message (including tool_calls) to history
            messages.append(msg)

            # Execute every requested tool and append results
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args: dict = json.loads(tc.function.arguments)
                result  = execute_tool(fn_name, fn_args)

                trace["tool_calls"].append({
                    "round":          round_num + 1,
                    "tool":           fn_name,
                    "args":           fn_args,
                    "result_preview": result[:160] + ("…" if len(result) > 160 else ""),
                })

                if verbose:
                    print(f"\n  🔧  Tool [{round_num+1}]: {fn_name}({fn_args})")
                    print(f"      Result: {result[:90]}…")

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })

        else:
            # Exhausted all tool rounds without a plain-text response
            trace["final_answer"] = "[Max tool rounds reached without a final answer]"

        return trace

    # ── Convenience ───────────────────────────────────────────────────────

    def model_info(self) -> dict:
        return {
            "model":           self.model,
            "max_tokens":      self.max_tokens,
            "temperature":     self.temperature,
            "top_k":           self.top_k,
            "max_tool_rounds": self.max_tool_rounds,
            "tools_registered":len(get_tool_schemas()),
        }