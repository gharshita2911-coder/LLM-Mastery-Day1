# AI CRM Assistant — Flask API server (Gemini-powered)

import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request

from llm_service import analyze_lead

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Middleware: request logger ────────────────────────────────────────────────
@app.before_request
def log_request():
    log.info("%s %s", request.method, request.path)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def home():
    return jsonify({
        "message": "AI CRM Assistant API is running successfully",
        "health_endpoint": "/health",
        "crm_endpoint": "/crm/analyze-lead",
        "status": "live"
    })

@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.post("/crm/analyze-lead")
def crm_analyze_lead():
    """
    POST /crm/analyze-lead
    Body : { name, company, notes }
    Response: { summary, suggestedFollowUp, sentimentScore }
    """
    data = request.get_json(silent=True) or {}

    # ── Input validation ──────────────────────────────────────────────────────
    errors = []

    name = data.get("name", "")
    if not isinstance(name, str) or not name.strip():
        errors.append("'name' is required and must be a non-empty string.")

    company = data.get("company", "")
    if not isinstance(company, str) or not company.strip():
        errors.append("'company' is required and must be a non-empty string.")

    notes = data.get("notes", "")
    if not isinstance(notes, str) or len(notes.strip()) < 10:
        errors.append(
            "'notes' is required and must be a string with at least 10 characters."
        )

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # ── LLM analysis ─────────────────────────────────────────────────────────
    try:
        result = analyze_lead(name.strip(), company.strip(), notes.strip())
        return jsonify(result), 200

    except ValueError as e:
        log.error("LLM output error: %s", e)
        return jsonify({"error": "Invalid LLM output.", "details": str(e)}), 500

    except Exception as e:
        err_str = str(e)
        log.error("Gemini API error: %s", err_str)

        if "API_KEY" in err_str or "INVALID_ARGUMENT" in err_str:
            return jsonify({"error": "Invalid Gemini API key. Check your .env file."}), 500
        if "429" in err_str or "quota" in err_str.lower():
            return jsonify({"error": "Gemini rate limit exceeded. Retry after a moment."}), 429

        return jsonify({"error": "Failed to analyze lead.", "details": err_str}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": f"Route not found: {request.method} {request.path}"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": f"Method not allowed: {request.method} {request.path}"}), 405


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    print(f"✅  AI CRM Assistant running on http://localhost:{port}")
    print(f"   Model : {model}")
    print(f"   Health: http://localhost:{port}/health")
    print(f"   POST  : http://localhost:{port}/crm/analyze-lead")

    app.run(host="0.0.0.0", port=port, debug=False)
