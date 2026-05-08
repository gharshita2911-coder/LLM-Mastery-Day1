import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

load_dotenv()


class GeminiService:

    def __init__(self):
        

        # Load multiple API keys
        self.api_keys = [
            os.getenv("GEMINI_API_KEY_1"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
            os.getenv("GEMINI_API_KEY_4")
        ]
        
        # Remove empty keys
        self.api_keys = [
            key for key in self.api_keys if key
        ]

        if not self.api_keys:
            raise Exception("No valid Gemini API keys found")

        self.model_name = "gemini-2.5-flash-lite"

    # ---------------- GENERIC GEMINI CALL ---------------- #

    def generate_response(self, prompt):

        last_error = None

        for key in self.api_keys:

            try:

                # Configure API key
                genai.configure(api_key=key)

                # Create model
                model = genai.GenerativeModel(
                    self.model_name
                )

                # Generate response
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0
                    }
                )

                # TOKEN LOGGING
                usage = response.usage_metadata

                print("\n===== TOKEN USAGE =====")
                print(
                    "Prompt Tokens:",
                    usage.prompt_token_count
                )

                print(
                    "Completion Tokens:",
                    usage.candidates_token_count
                )

                print(
                    "Total Tokens:",
                    usage.total_token_count
                )

                return response.text

            except Exception as e:

                last_error = str(e)

                print(f"API key failed: {e}")

                continue

        raise Exception(
            f"All API keys exhausted: {last_error}"
        )

    # ---------------- CHAT RESPONSE ---------------- #

    def get_chat_response(self, user_message):

        response_text = self.generate_response(
            user_message
        )

        return {
            "message": response_text
        }

    # ---------------- EXTRACTION ---------------- #

    def extract_data(self, user_text):

        MAX_LENGTH = 1000

        if len(user_text) > MAX_LENGTH:

            return {
                "error": f"Input exceeds {MAX_LENGTH} characters"
            }


        prompt = f"""
        Extract name, email, summary, and sentiment.

        Return ONLY valid JSON:

        {{
            "name": null,
            "email": null,
            "summary": null,
            "sentiment": null
        }}

        Rules:
        - Select first name/email only
        - summary should be very short 8 words max
        -- if sentiment is unclear, return neutral never return mixed
        Text:{user_text}
        """
        try:

            response_text = self.generate_response(
                prompt
            )

            # Remove markdown formatting
            response_text = response_text.replace(
                "```json", ""
            )

            response_text = response_text.replace(
                "```", ""
            )

            response_text = response_text.strip()

            print("\n===== GEMINI RESPONSE =====")
            print(response_text)

            result = json.loads(response_text)

            self.validate_result(result)

            return result

        except Exception as e:

            return {
                "error": str(e)
            }

    # ---------------- VALIDATION ---------------- #

    def validate_result(self,result):
        required_fields = ["name", "email", "summary", "sentiment"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
            if field == "sentiment" and result[field] not in ["positive", "negative", "neutral",None]:
                raise ValueError(f"Invalid sentiment value: {result[field]}")
                
            if len(required_fields) != 4:
                raise ValueError("Result must contain exactly 4 fields: name, email, summary, and sentiment")