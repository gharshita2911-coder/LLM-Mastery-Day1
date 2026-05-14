from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from rag_service import RAGService
import os

app = Flask(__name__)

# Lazy init — created on first request, not at import time
# This prevents crash-on-startup if API key is missing
rag_service = None

ALLOWED_EXTENSIONS  = {"txt", "md"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def get_rag():
    global rag_service
    if rag_service is None:
        rag_service = RAGService()
    return rag_service


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ── GET / ─────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "message": "RAG Knowledge Base API is running"}, 200


# ── POST /upload ───────────────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "document" not in request.files:
            return {"error": "No file part. Use field name 'document'"}, 400

        file = request.files["document"]

        if not file or file.filename == "":
            return {"error": "No file selected"}, 400

        if not allowed_file(file.filename):
            return {"error": f"Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}"}, 400

        filename   = secure_filename(file.filename)
        file_bytes = file.read()

        if len(file_bytes) == 0:
            return {"error": "File is empty"}, 400

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            return {"error": "File exceeds 5 MB limit"}, 400

        result = get_rag().ingest_document(file_bytes, filename)

        if "error" in result:
            return result, 400

        return result, 200

    except Exception as e:
        return {"error": "Upload failed", "details": str(e)}, 500


# ── POST /ask ──────────────────────────────────────────────────────────────
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()

        if not data:
            return {"error": "JSON body is missing"}, 400

        question = data.get("question", "").strip()

        if not question:
            return {"error": "question field is required"}, 400

        if len(question) > 1000:
            return {"error": "Question exceeds 1000 characters"}, 400

        svc = get_rag()

        if svc.vector_store.is_empty():
            return {"error": "No documents uploaded yet. POST a file to /upload first."}, 400

        result = svc.answer_question(question)

        if "error" in result:
            return result, 400

        return result, 200

    except Exception as e:
        msg = str(e)
        if "api key" in msg.lower():
            return {"error": "Invalid or missing API key"}, 401
        if "quota" in msg.lower() or "rate limit" in msg.lower():
            return {"error": "Rate limit exceeded"}, 429
        return {"error": "Something went wrong", "details": msg}, 500


# ── GET /status ────────────────────────────────────────────────────────────
@app.route("/status", methods=["GET"])
def status():
    try:
        stats = get_rag().vector_store.get_stats()
        return stats, 200
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7000))
    app.run(host="0.0.0.0", debug=True, port=port)
