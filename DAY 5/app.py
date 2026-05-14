from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from rag_service import RAGService
import os

app = Flask(__name__)
rag_service = RAGService()

# Allowed file types for upload
ALLOWED_EXTENSIONS = {"txt", "md", "pdf"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ─────────────────────────────────────────────
# POST /upload
# Accepts: multipart/form-data with file field "document"
# Returns: { "success": true, "doc_id": "...", "chunks_stored": N }
# ─────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "document" not in request.files:
            return jsonify({"error": "No file part in request. Use field name 'document'"}), 400

        file = request.files["document"]

        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({
                "error": f"Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}"
            }), 400

        filename = secure_filename(file.filename)
        file_bytes = file.read()

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            return jsonify({
                "error": f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB"
            }), 400

        result = rag_service.ingest_document(file_bytes, filename)

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Upload failed", "details": str(e)}), 500


# ─────────────────────────────────────────────
# POST /ask
# Body: { "question": "..." }
# Returns: { "answer": "...", "sources": [ { "chunkId": "...", "snippet": "..." } ] }
# ─────────────────────────────────────────────
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "JSON body is missing"}), 400

        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "Question field is required"}), 400

        if len(question) > 1000:
            return jsonify({"error": "Question exceeds 1000 characters"}), 400

        if rag_service.vector_store.is_empty():
            return jsonify({
                "error": "No documents uploaded yet. Please upload documents first."
            }), 400

        result = rag_service.answer_question(question)

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        error_message = str(e)
        print("Error:", error_message)

        if "api key" in error_message.lower():
            return jsonify({"error": "Invalid or missing API key"}), 401
        elif "quota" in error_message.lower() or "rate limit" in error_message.lower():
            return jsonify({"error": "Quota or rate limit exceeded"}), 429

        return jsonify({"error": "Something went wrong", "details": error_message}), 500


# ─────────────────────────────────────────────
# GET /status
# Returns: current vector store stats
# ─────────────────────────────────────────────
@app.route("/status", methods=["GET"])
def status():
    stats = rag_service.vector_store.get_stats()
    return jsonify(stats), 200


if __name__ == "__main__":
    app.run(debug=True, port=7000)
