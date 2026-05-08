from flask import Flask,request,jsonify
from gemini_service import GeminiService
gemini_service=GeminiService()

app=Flask(__name__)

##CHAT ENDPOINT
@app.route("/chat",methods=["POST"])
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
        
        result=gemini_service.get_chat_response(user_message)
        
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

##EXTRACT ENDPOINT
@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json()
    if not data:
        return jsonify({
            "error": "JSON body is missing"
        }), 400
    user_text = data.get("text")
    if not user_text:
        return jsonify({
            "error": "Text field is required"
        }), 400
    try:
        result = gemini_service.extract_data(user_text)
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "error": "Something went wrong",
            "details": str(e)
        }), 500

# Start Flask server
if __name__ == "__main__":

    app.run(debug=True, port=4000)

