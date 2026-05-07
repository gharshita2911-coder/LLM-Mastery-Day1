from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load .env variables
load_dotenv()

app = Flask(__name__)

# Get API key
api_key = os.getenv("OPENAI_API_KEY")

# Check if API key exists
if not api_key:
    raise Exception("OPENAI_API_KEY is missing")

# Create OpenAI client
client = OpenAI(api_key=api_key)


# Function to get AI response
def get_chat_response(user_message):

    response = client.chat.completions.create(
        model="gpt-4o-mini",

        messages=[
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    return {
        "message": response.choices[0].message.content,

        "tokens": {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens
        }
    }


# POST endpoint
@app.route("/chat", methods=["POST"])
def chat():

    try:

        # Read JSON body
        data = request.get_json()

        # Validate JSON
        if not data:
            return jsonify({
                "error": "JSON body is missing"
            }), 400

  
        user_message = data.get("message")

        result = get_chat_response(user_message)

        return jsonify({
            "response": result["message"],
            "tokens": result["tokens"]
        }), 200

    # OpenAI API key errors
    except Exception as e:

        error_message = str(e)
        print("Error:", error_message)

          # Validating message
        if not user_message:
            return jsonify({
                "error": "Message is required"
            }), 400

        # Missing or invalid API key
        elif "api_key" in error_message.lower() or "api key" in error_message.lower():

            return jsonify({
                "error": "Invalid or missing API key"
            }), 401

        # Rate limit error
        elif "rate limit" in error_message.lower():

            return jsonify({
                "error": "Rate limit exceeded"
            }), 429

        elif "quota" in error_message.lower():
            return jsonify({
                "error":"Quota limit exceeded"
            }),429
        # Generic server error
        return jsonify({
            "error": "Something went wrong",
            "details": error_message
        }), 500


# Start Flask server
if __name__ == "__main__":

    app.run(debug=True, port=4000)