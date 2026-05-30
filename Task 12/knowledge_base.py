"""
knowledge_base.py
=================
Built-in seed documents for the RAG system.

This file does two things:
  1. Defines DOCUMENTS — a list of dicts the RAGEngine can ingest directly.
  2. Exposes seed_engine(engine) — called by main.py to load these docs
     into any RAGEngine instance before it is built.

To add a permanent built-in document: append to DOCUMENTS below.
To add a file-based document at runtime: use engine.ingest_file() in main.py.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag_engine import RAGEngine

# ─────────────────────────────────────────────────────────────────────────────
# Built-in documents
# ─────────────────────────────────────────────────────────────────────────────

DOCUMENTS: list[dict] = [
    {
        "id": "doc_001",
        "title": "Introduction to Transformer Architecture",
        "content": (
            "The Transformer architecture was introduced in the 2017 paper "
            "'Attention Is All You Need' by Vaswani et al. "
            "It relies entirely on self-attention mechanisms rather than recurrent "
            "or convolutional layers. "
            "The model consists of an encoder and a decoder, each composed of "
            "stacked identical layers. "
            "Each encoder layer has two sub-layers: multi-head self-attention and "
            "a position-wise feed-forward network. "
            "Positional encodings are added to input embeddings to inject sequence "
            "order information. "
            "The scaled dot-product attention computes: "
            "Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) * V. "
            "Multi-head attention allows the model to attend to information from "
            "different representation subspaces simultaneously."
        ),
    },
    {
        "id": "doc_002",
        "title": "Retrieval-Augmented Generation (RAG)",
        "content": (
            "RAG combines parametric knowledge stored in model weights with "
            "non-parametric retrieval from external documents. "
            "A RAG system embeds user queries and documents into a shared vector space. "
            "At inference time, the top-k most similar document chunks are retrieved "
            "using cosine similarity or approximate nearest-neighbour (ANN) search. "
            "Retrieved chunks are concatenated into the context window alongside the "
            "user question. "
            "This allows LLMs to cite sources, reduce hallucination, and access "
            "knowledge beyond their training cutoff. "
            "Common vector stores used in RAG include FAISS, Pinecone, Weaviate, "
            "and Chroma. "
            "Chunk size and overlap are critical hyperparameters: smaller chunks "
            "improve precision, larger chunks improve context continuity."
        ),
    },
    {
        "id": "doc_003",
        "title": "Function Calling in Large Language Models",
        "content": (
            "Function calling (also called tool use) allows LLMs to invoke external "
            "functions during generation. "
            "The model receives a JSON schema describing available tools — name, "
            "description, and parameter types. "
            "When the model decides a tool is needed, it outputs a structured JSON "
            "call instead of plain text. "
            "The application executes the function and returns the result to the model "
            "as a tool-role message. "
            "The model then incorporates the result into its final answer. "
            "Groq's function calling API follows the OpenAI tool-call format with "
            "tool_choice='auto' support. "
            "Function calling enables real-time data lookup, computation, and actions "
            "beyond the model's static knowledge."
        ),
    },
    {
        "id": "doc_004",
        "title": "Vector Embeddings and Similarity Search",
        "content": (
            "Embeddings are dense vector representations of text learned by neural "
            "networks. "
            "The all-MiniLM-L6-v2 model from sentence-transformers produces "
            "384-dimensional vectors suitable for semantic search. "
            "Cosine similarity measures the angle between two vectors: "
            "sim(A,B) = (A·B) / (||A|| × ||B||). "
            "When vectors are L2-normalised, dot product equals cosine similarity. "
            "Approximate Nearest Neighbour (ANN) algorithms like HNSW and IVF "
            "scale similarity search to billions of vectors efficiently. "
            "Bi-encoder models embed queries and documents independently — fast "
            "for large-scale retrieval. "
            "Cross-encoders jointly encode query and document for higher precision "
            "re-ranking of a smaller candidate set."
        ),
    },
    {
        "id": "doc_005",
        "title": "Groq API and LPU Inference",
        "content": (
            "Groq is an AI infrastructure company that builds Language Processing "
            "Units (LPUs) for ultra-fast LLM inference. "
            "The Groq API is OpenAI-compatible and supports chat completions, "
            "tool use, and JSON mode. "
            "Supported models include llama-3.3-70b-versatile, llama-3.1-8b-instant, "
            "and mixtral-8x7b-32768. "
            "Groq achieves 300–800 tokens per second, far exceeding GPU-based "
            "inference providers at comparable cost. "
            "The Python SDK mirrors the openai library: "
            "client = Groq(api_key=...); client.chat.completions.create(...). "
            "Tool calling follows the OpenAI format: pass tools as a list of "
            "JSON schema dicts. "
            "The free tier allows approximately 30 requests per minute on most models."
        ),
    },
    {
        "id": "doc_006",
        "title": "Prompt Engineering Best Practices",
        "content": (
            "Effective prompts provide clear task descriptions, relevant context, "
            "and explicit output format specifications. "
            "Chain-of-thought (CoT) prompting improves reasoning by asking models "
            "to show their work step by step before giving a final answer. "
            "Few-shot examples demonstrate the desired format and style directly "
            "in the prompt, reducing ambiguity. "
            "Role prompting — 'You are an expert in X' — can improve quality for "
            "domain-specific tasks. "
            "Instruction following improves when you are specific: prefer 'list "
            "three reasons' over 'explain'. "
            "Temperature controls randomness: 0 for deterministic outputs, "
            "1+ for creative generation. "
            "System prompts set persistent behaviour across a conversation, "
            "separate from user turns."
        ),
    },
    {
        "id": "doc_007",
        "title": "FAISS: Facebook AI Similarity Search",
        "content": (
            "FAISS is an open-source library developed by Meta AI for efficient "
            "similarity search and clustering of dense vectors. "
            "It supports exact search via IndexFlatL2 and IndexFlatIP, and "
            "approximate search via IndexIVFFlat and IndexHNSWFlat. "
            "IndexFlatIP performs exact inner-product search — equivalent to cosine "
            "similarity when vectors are L2-normalised. "
            "faiss.normalize_L2(vectors) normalises vectors in-place before adding. "
            "FAISS is written in C++ with Python bindings and optionally uses GPU. "
            "Build: create index, optionally train (for IVF), then call index.add(). "
            "Search: D, I = index.search(query_vec, k) returns distances D and "
            "indices I of the top-k nearest neighbours."
        ),
    },
    {
        "id": "doc_008",
        "title": "LLM Evaluation Metrics",
        "content": (
            "Evaluating LLMs requires both automated metrics and human judgment. "
            "BLEU and ROUGE measure n-gram overlap between generated and reference text. "
            "BERTScore uses contextual embeddings to compute semantic similarity "
            "between generation and reference, tolerating paraphrase. "
            "For RAG systems, retrieval quality is measured by Precision@k, Recall@k, "
            "and Mean Reciprocal Rank (MRR). "
            "Generation quality is assessed by faithfulness (does the answer match "
            "the retrieved context?) and answer relevance. "
            "Hallucination rate measures how often the model produces facts not "
            "supported by the retrieved context. "
            "LLM-as-judge frameworks use a powerful model to score outputs on rubrics "
            "such as correctness, completeness, and coherence."
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Seed function
# ─────────────────────────────────────────────────────────────────────────────

def seed_engine(engine: "RAGEngine") -> None:
    """
    Load all built-in DOCUMENTS into *engine*.
    Called by main.py at startup before engine.build().
    """
    for doc in DOCUMENTS:
        engine.add_document(
            text   = doc["content"],
            title  = doc["title"],
            doc_id = doc["id"],
            source = "builtin",
        )
