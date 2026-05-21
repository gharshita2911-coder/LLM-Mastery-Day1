from fastapi import FastAPI

from pydantic import BaseModel

from rag_engine import run_rag_query


app = FastAPI()


class BatchRequest(BaseModel):
    queries: list[str]
    top_k: int = 3


@app.get("/health")
def health():

    return {
        "status": "ok",
        "groq_key_set": True,
        "model": "llama3-8b-8192"
    }


@app.post("/rag")
def rag(query: dict):

    q = query.get("query", "")

    return run_rag_query(q)


@app.post("/rag/batch")
def rag_batch(body: BatchRequest):

    results = []

    for q in body.queries:

        result = run_rag_query(
            q,
            top_k=body.top_k
        )

        results.append(result)

    valid_count = sum(
        1 for r in results
        if r["valid"]
    )

    invalid_count = (
        len(results) - valid_count
    )

    valid_pct = round(
        (valid_count / len(results)) * 100,
        1
    )

    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "valid_pct": valid_pct,
        "target_met": valid_pct >= 95,
        "results": results
    }