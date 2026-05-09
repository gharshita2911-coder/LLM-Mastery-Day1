import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
from flask import Flask,request,jsonify

from lead_tool import tools
from lead_schema import lead_schema
from mock_lead import create_lead
from validator import validate_schema
from token_logger import log_token_usage

load_dotenv()

app = Flask(__name__)
api_keys = [
    key for key in [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3"),
        os.getenv("GEMINI_API_KEY_4"),
        os.getenv("GEMINI_API_KEY_5"),
        os.getenv("GEMINI_API_KEY_6"),
        os.getenv("GEMINI_API_KEY_7")
    ]if key
]
def generate_with_fallback(prompt):

    last_error = None

    for key in api_keys:

        try:

            genai.configure(api_key=key)

            temp_model = genai.GenerativeModel(
                model_name="gemini-2.5-flash-lite",
                tools=tools
            )

            response = temp_model.generate_content(prompt)

            return response

        except Exception as error:

            last_error = error
            continue
    raise Exception(f"All API keys failed: {last_error}")
    

SYSTEM_PROMPT = """
You are an intent classifier.

Call createLead When the user:
-explicitly asks to be contacted
- asks for callback
- wants to be added as a lead
Do Not call createLead tool if the user:
    - is only researching
    - comparing options
    - reading documentation
    - collecting information
    - says no action required
    - says not interested right now 
    - says maybe later
    - is exploring the market
    - is evaluating tools generally
    -Do not invent names or company names.
    -If not explicitly present, return null. 

If createLead is called then:
Extract name ,email,company if available. Message is always required.
Use null for any missing fields.
Summarise message in 1 short sentence
Never return free text as the main response.
"""

###  ------------------ ENDPOINT ------------------ ###
@app.route("/lead", methods=["POST"])
def detect_intent():
    try:
        data = request.get_json()

        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({
                "success": False,
                "error": "Message field is required"
            }), 400

        response = generate_with_fallback([
            SYSTEM_PROMPT,
            user_message
        ])

        # log token usage
        if response.usage_metadata:
            log_token_usage(response.usage_metadata)

        candidate = response.candidates[0]

        function_call = None

        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                break

        # token response
        token_data = {
            "prompt": response.usage_metadata.prompt_token_count,
            "completion": response.usage_metadata.candidates_token_count,
            "total": response.usage_metadata.total_token_count
        }

        # NO TOOL CALL
        if not function_call:
            return jsonify({
                "action": "none",
                "args": {
                    "name": None,
                    "email": None,
                    "company": None,
                    "message": user_message
                },
                "tokens": token_data
            })

        # TOOL CALL EXISTS
        args = dict(function_call.args)

        validation_result = validate_schema(
            data=args,
            schema=lead_schema
        )

        if not validation_result["valid"]:
            return jsonify({
                "success": False,
                "error": validation_result["errors"]
            }), 400

        # save lead
        create_lead(args)

        return jsonify({
            "action": "createLead",
            "args": {
                "name": args.get("name", None),
                "email": args.get("email", None),
                "company": args.get("company", None),
                "message": user_message
            },
            "tokens": token_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__=="__main__":
    app.run(debug=True,port=5000)