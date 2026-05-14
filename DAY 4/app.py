from flask import Flask, request, jsonify
from email_service import EmailService
import os

app = Flask(__name__)
email_service = None          # lazy — created on first request

MAX_EMAIL_LENGTH = 8000  # characters


def get_service():
    global email_service
    if email_service is None:
        email_service = EmailService()
    return email_service


@app.route("/email/analyze", methods=["POST"])
def analyze_email():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "JSON body is missing"
            }), 400

        email_text = data.get("email", "").strip()

        if not email_text:
            return jsonify({
                "error": "Email field is required"
            }), 400

        if len(email_text) > MAX_EMAIL_LENGTH:
            return jsonify({
                "error": f"Email exceeds maximum length of {MAX_EMAIL_LENGTH} characters"
            }), 400

        result = get_service().analyze_email(email_text)

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        error_message = str(e)
        print("Error:", error_message)

        if "api key" in error_message.lower():
            return jsonify({
                "error": "Invalid or missing API key"
            }), 401

        elif "quota" in error_message.lower() or "rate limit" in error_message.lower():
            return jsonify({
                "error": "Quota or rate limit exceeded"
            }), 429

        return jsonify({
            "error": "Something went wrong",
            "details": error_message
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 6000))
    app.run(host="0.0.0.0", port=port)
