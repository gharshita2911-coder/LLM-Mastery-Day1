import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
from token_logger import log_token_usage

load_dotenv()

# Gemini pricing (as of 2025) for gemini-2.5-flash-lite
# Input:  $0.10 / 1M tokens
# Output: $0.40 / 1M tokens
COST_PER_INPUT_TOKEN  = 0.10 / 1_000_000
COST_PER_OUTPUT_TOKEN = 0.40 / 1_000_000


class EmailService:

    def __init__(self):
        self.api_keys = [
            key for key in [
                os.getenv("GEMINI_API_KEY_1"),
                os.getenv("GEMINI_API_KEY_2"),
                os.getenv("GEMINI_API_KEY_3"),
                os.getenv("GEMINI_API_KEY_4"),
            ]
            if key
        ]

        if not self.api_keys:
            raise Exception("No valid Gemini API keys found")

        self.model_name = "gemini-2.5-flash-lite"

    # ---------------- GENERIC GEMINI CALL ---------------- #

    def generate_response(self, prompt):
        last_error = None

        for key in self.api_keys:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(self.model_name)

                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0}
                )

                usage = response.usage_metadata
                print("\n===== TOKEN USAGE =====")
                print("Prompt Tokens    :", usage.prompt_token_count)
                print("Completion Tokens:", usage.candidates_token_count)
                print("Total Tokens     :", usage.total_token_count)

                return response

            except Exception as e:
                last_error = str(e)
                print(f"API key failed: {e}")
                continue

        raise Exception(f"All API keys exhausted: {last_error}")

    # ---------------- COST CALCULATION ---------------- #

    def calculate_cost(self, prompt_tokens, completion_tokens):
        cost = (
            prompt_tokens     * COST_PER_INPUT_TOKEN +
            completion_tokens * COST_PER_OUTPUT_TOKEN
        )
        return round(cost, 8)   # keep 8 decimal places for micro-costs

    # ---------------- EMAIL ANALYSIS ---------------- #

    def analyze_email(self, email_text):
        prompt = f"""
You are an expert email analyst and professional writer.

Analyze the email below and return ONLY valid JSON — no markdown, no backticks, no preamble.

The JSON must have exactly these fields:

{{
    "tone": "<one of: formal, neutral, urgent, casual>",
    "summary": "<one sentence, max 20 words>",
    "suggestedReply": "<a complete, professional reply to the email>"
}}

Rules:
- "tone" must be exactly one of: formal, neutral, urgent, casual
- "summary" must be a single sentence of 20 words or fewer
- "suggestedReply" must be a ready-to-send reply (professional, polite, and relevant)
- Do NOT add any fields beyond the three listed above
- If the email is in a language other than English, detect the language and reply in the same language

Email:
{email_text}
"""

        try:
            response = self.generate_response(prompt)

            usage = response.usage_metadata
            prompt_tokens     = usage.prompt_token_count
            completion_tokens = usage.candidates_token_count
            total_tokens      = usage.total_token_count

            # Log tokens to file
            log_token_usage(usage)

            # Cost
            cost_usd = self.calculate_cost(prompt_tokens, completion_tokens)

            # Parse response
            response_text = response.text
            response_text = response_text.replace("```json", "").replace("```", "").strip()

            print("\n===== GEMINI RESPONSE =====")
            print(response_text)

            result = json.loads(response_text)

            # Validate
            self._validate_result(result)

            # Attach token + cost metadata
            result["tokens"] = {
                "prompt":     prompt_tokens,
                "completion": completion_tokens,
                "total":      total_tokens
            }
            result["cost_usd"] = cost_usd

            return result

        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse JSON response: {str(e)}"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    # ---------------- VALIDATION ---------------- #

    def _validate_result(self, result):
        required_fields = {"tone", "summary", "suggestedReply"}
        allowed_tones   = {"formal", "neutral", "urgent", "casual"}

        # Check no extra fields
        extra = set(result.keys()) - required_fields
        if extra:
            raise ValueError(f"Hallucinated fields detected: {extra}")

        # Check all required fields present
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")

        # Validate tone
        if result["tone"] not in allowed_tones:
            raise ValueError(
                f"Invalid tone '{result['tone']}'. Must be one of: {allowed_tones}"
            )

        # Validate summary length (word count ≤ 20)
        if result["summary"] and len(result["summary"].split()) > 25:
            raise ValueError("Summary exceeds 25 words")
