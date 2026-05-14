# Day 4 – AI Email Reply Generator API

A Flask API that analyzes emails and returns structured output: **tone**, **summary**, and a **suggested reply** — powered by Gemini 2.5 Flash Lite.

---

## API Contract

### `POST /email/analyze`

**Request body**
```json
{
  "email": "Your raw email text here..."
}
```

**Success response (200)**
```json
{
  "tone": "formal",
  "summary": "Customer requesting enterprise license pricing and demo.",
  "suggestedReply": "Dear Mr. Kapoor, Thank you for reaching out...",
  "tokens": {
    "prompt": 312,
    "completion": 118,
    "total": 430
  },
  "cost_usd": 0.00007920
}
```

**Error responses**

| Status | Reason |
|--------|--------|
| 400 | Missing/empty email or email exceeds 8000 characters |
| 401 | Invalid or missing API key |
| 429 | Quota or rate limit exceeded |
| 500 | Internal server error |

---

## Tone values

| Value | When used |
|-------|-----------|
| `formal` | Professional, business correspondence |
| `neutral` | Matter-of-fact, informational |
| `urgent` | Time-sensitive or escalated issues |
| `casual` | Informal, friendly messages |

---

## Local Setup

```bash
# 1. Clone / copy files
cd email_reply_generator

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env (do NOT commit this)
echo "GEMINI_API_KEY_1=your_key_here" > .env

# 4. Run the server
python app.py
# Server starts at http://127.0.0.1:6000
```

### Test with curl

```bash
curl -X POST http://127.0.0.1:6000/email/analyze \
  -H "Content-Type: application/json" \
  -d '{"email": "Hi, I need help with my account. It has been locked for two days."}'
```

---

## Deployment (Railway / Render)

1. Push code to GitHub (ensure `.env` is in `.gitignore`)
2. Create a new project on [Railway](https://railway.app) or [Render](https://render.com)
3. Set environment variables in the dashboard:
   - `GEMINI_API_KEY_1` = your key
4. Set start command: `python app.py`
5. Deploy — your public URL is ready

`.env.example` (commit this, not `.env`):
```
GEMINI_API_KEY_1=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=
```

---

## Running Tests

```bash
# Start server first (in one terminal)
python app.py

# Run tests (in another terminal)
python run_tests.py
```

Results are saved to `test_results.json`.

---

## Cost Per Request

Model: **gemini-2.5-flash-lite**

| Token type | Rate |
|------------|------|
| Input      | $0.10 / 1M tokens |
| Output     | $0.40 / 1M tokens |

**Formula:**
```
cost = (prompt_tokens × 0.10/1_000_000) + (completion_tokens × 0.40/1_000_000)
```

**Typical request (400 total tokens):**
- Prompt ~300 tokens → $0.000030
- Completion ~100 tokens → $0.000040
- **Total ≈ $0.000070 per request**

At this rate, **1,000 requests ≈ $0.07**

---

## Project Structure

```
email_reply_generator/
├── app.py            # Flask app + /email/analyze endpoint
├── email_service.py  # Gemini API calls, parsing, validation, cost calc
├── token_logger.py   # Logs token usage to token_usage.log
├── test_cases.json   # 20 test cases
├── run_tests.py      # Test runner with metrics
├── requirements.txt
├── .env.example
└── README.md
```

---

## How it builds on Days 1–3

| Day | Pattern reused |
|-----|----------------|
| Day 1 | API key rotation, token logging, error handling |
| Day 2 | Structured JSON output via prompt schema, validation |
| Day 3 | Modular service class, clean endpoint structure |
