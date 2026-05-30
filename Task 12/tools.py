"""
tools.py
========
All tool-related concerns in one place:

  TOOL_REGISTRY   — list of Groq-compatible JSON schemas (passed to the API)
  execute_tool()  — dispatcher: runs the right function for a given tool name
  register_tool() — add a new tool at runtime without touching this file

Adding a new tool:
  1. Define a Python function  my_fn(arg1, arg2, ...) -> str
  2. Call register_tool(schema_dict, my_fn)  anywhere before the first query
  That's it — the new tool is automatically included in every LLM call.
"""

from __future__ import annotations
import json
from typing import Callable

# ─────────────────────────────────────────────────────────────────────────────
# Internal registry  {name -> (schema_dict, callable)}
# ─────────────────────────────────────────────────────────────────────────────
_REGISTRY: dict[str, tuple[dict, Callable]] = {}


def register_tool(schema: dict, fn: Callable) -> None:
    """
    Register a tool at runtime.

    Parameters
    ----------
    schema : dict
        OpenAI/Groq function-calling schema:
        {
          "type": "function",
          "function": {
            "name": "...",
            "description": "...",
            "parameters": { "type": "object", "properties": {...}, "required": [...] }
          }
        }
    fn : Callable
        Python function to call when the model invokes this tool.
        Must accept **kwargs matching the schema's parameter names.
    """
    name = schema["function"]["name"]
    _REGISTRY[name] = (schema, fn)


def get_tool_schemas() -> list[dict]:
    """Return the list of all registered tool schemas (passed directly to Groq)."""
    return [schema for schema, _ in _REGISTRY.values()]


def execute_tool(name: str, args: dict) -> str:
    """
    Dispatch a tool call by name.

    Returns the tool result as a plain string (fed back to the LLM as a
    tool-role message).  Never raises — errors are returned as strings so
    the LLM can gracefully handle them.
    """
    if name not in _REGISTRY:
        return f"[ToolError] Unknown tool '{name}'. Available: {list(_REGISTRY.keys())}"
    try:
        _, fn = _REGISTRY[name]
        return fn(**args)
    except Exception as exc:
        return f"[ToolError] '{name}' raised {type(exc).__name__}: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Built-in tool 1 — fetch_additional_doc
# ─────────────────────────────────────────────────────────────────────────────

# External data store — simulates a live external source.
# Keys here are the values the model can pass as the `topic` argument.
# Add new topics here; the schema enum is built dynamically.
EXTERNAL_DATA: dict[str, dict] = {
    "latest_model_benchmarks": {
        "title": "Latest LLM Benchmark Results (2024–2025)",
        "content": (
            "As of early 2025: GPT-4o scores 88.7 on MMLU, Gemini 1.5 Pro 85.9, "
            "Llama 3.3 70B 86.0 (strongest open-source). "
            "On HumanEval (code): Claude 3.5 Sonnet leads at 92%, GPT-4o at 90.2%. "
            "Groq serves Llama 3.3 70B at ~600 tok/s on LPU hardware. "
            "Multimodal benchmarks (MMMU): Gemini Ultra 59.4%, GPT-4V 56.8%."
        ),
    },
    "rag_frameworks_comparison": {
        "title": "RAG Frameworks Comparison 2025",
        "content": (
            "LangChain: most popular, 80k+ GitHub stars, broad ecosystem. "
            "LlamaIndex: specialises in structured data ingestion and query engines. "
            "Haystack (deepset): production-ready REST pipelines, strong enterprise adoption. "
            "DSPy (Stanford): programmatic prompt optimisation, compiles prompts automatically. "
            "Cohere Coral: grounded generation built in. "
            "2025 trend: agentic RAG — iterative retrieval and reasoning loops. "
            "All frameworks support Groq via OpenAI-compatible API."
        ),
    },
    "groq_pricing": {
        "title": "Groq API Pricing (2025)",
        "content": (
            "Llama 3.3 70B Versatile : $0.59 / 1M input tokens, $0.79 / 1M output. "
            "Llama 3.1 8B Instant    : $0.05 / 1M input tokens, $0.08 / 1M output. "
            "Mixtral 8x7B            : $0.24 / 1M input tokens, $0.24 / 1M output. "
            "Free tier: 30 RPM, 14,400 RPD per model. No per-request fees."
        ),
    },
    "python_faiss_install": {
        "title": "Installing and Using FAISS in Python",
        "content": (
            "Install: `pip install faiss-cpu`  (or faiss-gpu for CUDA). "
            "Create index: `index = faiss.IndexFlatIP(dim)`. "
            "Normalise first for cosine: `faiss.normalize_L2(vectors)`. "
            "Add vectors: `index.add(vectors)`. "
            "Search: `D, I = index.search(query, k)` — D=distances, I=indices. "
            "Persist: `faiss.write_index(index, 'store.index')` / `faiss.read_index(...)`. "
            "Production: use IndexIVFFlat with nlist ≈ sqrt(n) for large corpora."
        ),
    },
}


def _fetch_additional_doc(topic: str) -> str:
    doc = EXTERNAL_DATA.get(topic)
    if doc:
        return f"[{doc['title']}]\n{doc['content']}"
    available = ", ".join(EXTERNAL_DATA.keys())
    return f"[ToolError] No document for topic '{topic}'. Available: {available}"


register_tool(
    schema={
        "type": "function",
        "function": {
            "name": "fetch_additional_doc",
            "description": (
                "Fetch an up-to-date reference document from an external source "
                "when the retrieved KB context does not contain enough information. "
                "Use this for benchmark scores, API pricing, framework comparisons, "
                "or installation guides."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic key of the document to fetch.",
                        "enum": list(EXTERNAL_DATA.keys()),
                    }
                },
                "required": ["topic"],
            },
        },
    },
    fn=_fetch_additional_doc,
)


# ─────────────────────────────────────────────────────────────────────────────
# Built-in tool 2 — search_web
# ─────────────────────────────────────────────────────────────────────────────

_WEB_SIM: dict[str, str] = {
    "transformer":  "Web: 'Attention Is All You Need' has 70k+ citations (2025). Variants: BERT, GPT, T5, LLaMA, Mistral.",
    "groq":         "Web: Groq launched its LPU chip in 2023. GroqCloud public API available since 2024.",
    "llama":        "Web: Meta released Llama 3.3 70B in late 2024. Available free on Groq, Together, and Replicate.",
    "python":       "Web: Python 3.13 released Oct 2024. Adds JIT compiler (experimental) and improved error messages.",
}


def _search_web(query: str) -> str:
    q_lower = query.lower()
    for kw, result in _WEB_SIM.items():
        if kw in q_lower:
            return result
    return f"Web search '{query}': no simulated result found. Try a more specific query."


register_tool(
    schema={
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Simulate a live web search for very recent or highly specific "
                "information not found in the knowledge base or external documents. "
                "Use as a last resort when other tools cannot answer the question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query string.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    fn=_search_web,
)


# ─────────────────────────────────────────────────────────────────────────────
# Built-in tool 3 — summarise_document
# ─────────────────────────────────────────────────────────────────────────────

def _summarise_document(doc_id: str, max_sentences: int = 3) -> str:
    """
    Return the first `max_sentences` sentences of a document already in the
    knowledge base.  Useful when the model wants a quick overview without
    a full retrieval pass.
    """
    # This function is called by the LLM; we import lazily to avoid a
    # circular dependency (rag_engine → tools → rag_engine).
    try:
        from rag_engine import RAGEngine   # noqa: F401 — type check only
        # The engine instance is injected at runtime via _set_engine()
        engine = _ENGINE_REF.get("engine")
        if engine is None:
            return "[ToolError] RAG engine not initialised yet."
        docs = {d["id"]: d for d in engine.list_documents()}
        if doc_id not in docs:
            available = ", ".join(docs.keys())
            return f"[ToolError] Document '{doc_id}' not found. Available: {available}"
        # Find chunks for this doc and return first few sentences
        chunks = [c for c in engine.chunks if c["doc_id"] == doc_id]
        if not chunks:
            return f"[ToolError] No chunks found for doc '{doc_id}'."
        text = chunks[0]["text"]
        sentences = text.split(". ")
        summary = ". ".join(sentences[:max_sentences])
        if not summary.endswith("."):
            summary += "."
        return f"[Summary of {docs[doc_id]['title']}]\n{summary}"
    except Exception as e:
        return f"[ToolError] summarise_document: {e}"


# Mutable ref so llm_client can inject the live engine instance
_ENGINE_REF: dict = {"engine": None}


def set_engine_ref(engine) -> None:
    """Called by llm_client / main to give tools access to the live RAGEngine."""
    _ENGINE_REF["engine"] = engine


register_tool(
    schema={
        "type": "function",
        "function": {
            "name": "summarise_document",
            "description": (
                "Return a short summary of a specific document that is already loaded "
                "in the knowledge base. Use when the user asks what a particular "
                "document is about or requests an overview of a specific file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "The document ID to summarise (e.g. 'doc_001', 'file_abc123').",
                    },
                    "max_sentences": {
                        "type": "integer",
                        "description": "Maximum number of sentences to include (default 3).",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    fn=_summarise_document,
)
