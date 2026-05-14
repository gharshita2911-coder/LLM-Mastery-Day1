# Day 5 – AI Knowledge Base Assistant (RAG)

A Flask API that ingests documents, builds a vector index, and answers questions with cited source chunks — strictly grounded in the uploaded content.

---

## Architecture

```
Upload Flow:
  File → decode text → clean → chunk (400 chars, 80 overlap)
       → embed each chunk (Gemini text-embedding-004)
       → store in in-memory vector store

Ask Flow:
  Question → embed (Gemini text-embedding-004)
           → cosine similarity search → top-4 chunks
           → build grounded prompt → Gemini 2.5 Flash Lite
           → parse JSON → validate sources → return
```

**No external vector DB required** — pure Python cosine similarity.

---

## Project Structure

```
knowledge_base/
├── app.py              # Flask app – /upload, /ask, /status
├── rag_service.py      # Chunking, embedding, retrieval, answer generation
├── vector_store.py     # In-memory cosine-similarity vector DB
├── token_logger.py     # Logs token usage per request
├── test_cases.json     # 20 Q&A tests (15 answerable, 5 unanswerable)
├── run_tests.py        # Test runner with accuracy + hallucination metrics
├── requirements.txt
├── .env.example
├── README.md
└── sample_docs/
    ├── hr_policy.txt       # TechNova HR policy document
    └── novacrm_docs.txt    # NovaCRM technical documentation
```

---

## API Reference

### `POST /upload`
Upload a document to the knowledge base.

**Request:** `multipart/form-data`, field name: `document`  
Supported types: `.txt`, `.md`, `.pdf` (max 5 MB)

**Response (200)**
```json
{
  "success": true,
  "doc_id": "a3f2c1b0",
  "filename": "hr_policy.txt",
  "chunks_stored": 12,
  "total_chars": 3200
}
```

---

### `POST /ask`
Ask a question against all uploaded documents.

**Request**
```json
{ "question": "How many days of annual leave are employees entitled to?" }
```

**Response (200) — answer found**
```json
{
  "answer": "Employees are entitled to 18 days of paid annual leave per calendar year.",
  "sources": [
    {
      "chunkId": "a3f2c1b0_chunk_0",
      "snippet": "Employees are entitled to 18 days of paid annual leave per calendar year."
    }
  ],
  "tokens": { "prompt": 520, "completion": 95, "total": 615 },
  "cost_usd": 0.00009010
}
```

**Response (200) — answer not in documents**
```json
{
  "answer": "I cannot find relevant information in the uploaded documents to answer this question.",
  "sources": [],
  "tokens": null,
  "cost_usd": 0.0
}
```

---

### `GET /status`
Returns current vector store statistics.

```json
{
  "total_chunks": 24,
  "documents": [
    { "filename": "hr_policy.txt", "chunks": 12 },
    { "filename": "novacrm_docs.txt", "chunks": 12 }
  ]
}
```

---

## Local Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env
echo "GEMINI_API_KEY_1=your_key_here" > .env

# 3. Start server
python app.py
# → http://127.0.0.1:7000
```

### Upload a doc with curl
```bash
curl -X POST http://127.0.0.1:7000/upload \
  -F "document=@sample_docs/hr_policy.txt"
```

### Ask a question
```bash
curl -X POST http://127.0.0.1:7000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the notice period for senior employees?"}'
```

---

## Running Tests

```bash
# Terminal 1
python app.py

# Terminal 2
python run_tests.py
```

Results saved to `test_results.json`.

---

## Hallucination Prevention

Two layers of grounding:

1. **Similarity threshold (0.45):** If the best retrieved chunk scores below this, the model is never called — the API immediately returns "cannot find."
2. **Strict prompt:** Model is instructed to answer only from provided context. If the answer is absent, it must return the exact "cannot find" phrase.
3. **Source validation:** After generation, all cited `chunkId` values are validated against the actually-retrieved set. Phantom IDs are stripped.

---

## Cost Per Request

Model: **gemini-2.5-flash-lite**

| Token type | Rate |
|------------|------|
| Input | $0.10 / 1M tokens |
| Output | $0.40 / 1M tokens |

Typical ask request (~600 tokens total): **≈ $0.00009 per question**

---

## How it builds on Days 1–4

| Day | Pattern reused |
|-----|----------------|
| Day 1 | API key rotation, token logging, error handling |
| Day 2 | Structured JSON output, field validation |
| Day 3 | Modular service classes |
| Day 4 | Cost calculation, temperature=0, input length limits |
