from google import genai
from dotenv import load_dotenv
import os
from flask import Flask,request,jsonify

load_dotenv()
genapp=Flask(__name__)

api_key=os.getenv("Gemini_API_Key")

if not api_key:
    raise Exception("Gemini APi Key invalid")

client=genai.Client(api_key= api_key)

def get_chat_response(user_message):

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message
    )

    # Token metadata
    usage = response.usage_metadata

    prompt_tokens = usage.prompt_token_count
    completion_tokens = usage.candidates_token_count
    total_tokens = usage.total_token_count

    # Log tokens
    print("Prompt Tokens:", prompt_tokens)
    print("Completion Tokens:", completion_tokens)
    print("Total Tokens:", total_tokens)

    return {
        "message": response.text,

        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens
        }
    }
@genapp.route("/chat",methods=["POST"])
def chat():
    try:
        data=request.get_json()
        if not data:
            return({
                "error":"JSON body is missing"
            }),400
        user_message=data.get("message")

        if not user_message:
            return jsonify({
                "error":"Message is required"
            }),400
        
        result=get_chat_response(user_message)
        
        return jsonify({
            "response": result["message"],
            "tokens": result["tokens"]
        })

    except Exception as e:
        error_message=str(e)
        print("Error: ",error_message)

        if "api key" in error_message.lower():

            return jsonify({
                "error": "Invalid or missing API key"
            }), 401

        # Quota/rate limit
        elif "quota" in error_message.lower() or "rate limit" in error_message.lower():

            return jsonify({
                "error": "Quota or rate limit exceeded"
            }), 429

        # Generic server error
        return jsonify({
            "error": "Something went wrong",
            "details": error_message
        }), 500


# Start Flask server
if __name__ == "__main__":

    genapp.run(debug=True, port=4000)

