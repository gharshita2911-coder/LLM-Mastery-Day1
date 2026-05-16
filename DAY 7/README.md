#  AI CRM Assistant (Python + Gemini)

An AI-powered CRM lead analyzer built with **Python**, **Flask**, and **Google Gemini API**. Given a lead's name, company, and sales notes, it returns a structured JSON with a summary, suggested follow-up action, and sentiment score — all in a **single LLM call**.

---

##  Features

| Feature | Detail |
|---|---|
| **Lead Summary** | 2–3 sentence AI-generated summary of the lead's situation |
| **Suggested Follow-Up** | One concrete, actionable next step with a timeframe |
| **Sentiment Score** | `positive` / `neutral` / `negative` |
| **Structured Output** | Always returns clean JSON — no parsing guesswork |
| **Input Validation** | Descriptive 400 errors for missing or invalid fields |
| **Single LLM Call** | All three outputs generated in one efficient Gemini API call |
| **12 Test Cases** | Functional, edge case, and validation tests — stdlib only |

---

## Quick Start (One Command)

### 1. Clone and install

```bash
git clone <your-repo-url>
cd ai-crm-assistant
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your Gemini API key
```

**.env file:**
```env
GEMINI_API_KEY=your-gemini-api-key-here
PORT=3000
GEMINI_MODEL=gemini-1.5-flash
```

> Get your free API key at: https://aistudio.google.com/app/apikey

### 3. Start the server

```bash
python app.py
```

You should see:
```
✅  AI CRM Assistant running on http://localhost:3000
   Model : gemini-1.5-flash
   Health: http://localhost:3000/health
   POST  : http://localhost:3000/crm/analyze-lead
```

---

##  API Reference

### `POST /crm/analyze-lead`

Analyzes a CRM lead and returns a structured AI analysis.

**Request Body**

```json
{
  "name": "Priya Sharma",
  "company": "NovaTech Solutions",
  "notes": "Priya attended our webinar and immediately booked a demo. Budget already approved. She wants to switch by Q3."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Lead's full name |
| `company` | string | ✅ | Lead's company name |
| `notes` | string | ✅ | Sales notes (min 10 characters) |

**Success Response — `200 OK`**

```json
{
  "summary": "Priya Sharma from NovaTech Solutions is a high-priority lead who attended a webinar and has already secured budget approval for switching tools by Q3. Her current solution costs $20k/year, providing clear financial motivation. She has proactively booked a demo, signaling strong intent to move forward quickly.",
  "suggestedFollowUp": "Send a personalized demo confirmation email within 24 hours highlighting cost savings and the Q3 migration timeline, and include a one-page ROI comparison.",
  "sentimentScore": "positive"
}
```

| Field | Type | Values |
|---|---|---|
| `summary` | string | 2–3 sentence lead overview |
| `suggestedFollowUp` | string | One concrete next action |
| `sentimentScore` | string | `"positive"` \| `"neutral"` \| `"negative"` |

**Error Response — `400 Bad Request`**

```json
{
  "error": "Validation failed",
  "details": [
    "'name' is required and must be a non-empty string.",
    "'notes' is required and must be a string with at least 10 characters."
  ]
}
```

---

### `GET /health`

```json
{
  "status": "ok",
  "model": "gemini-1.5-flash",
  "timestamp": "2025-05-16T10:30:00+00:00"
}
```

---

## 🧪 Running Tests

Start the server in one terminal, then in another:

```bash
python test_crm.py
```

Optional — test against a different host:
```bash
BASE_URL=http://localhost:5000 python tests/test_crm.py
```

### Test Cases

| # | Test | Type |
|---|---|---|
| TC01 | Positive lead — strong interest & demo scheduled | Functional |
| TC02 | Negative lead — uninterested, no budget | Functional |
| TC03 | Neutral lead — exploratory multi-vendor evaluation | Functional |
| TC04 | Enterprise lead — multi-team compliance process | Functional |
| TC05 | Urgent lead — deadline + approved budget | Functional |
| TC06 | Minimal valid notes (just above 10-char minimum) | Functional |
| TC07 | Long notes with mixed signals | Functional |
| TC08 | International lead — non-ASCII company name | Functional |
| TC09 | Missing `name` field → 400 | Validation |
| TC10 | Missing `company` field → 400 | Validation |
| TC11 | Notes too short (< 10 chars) → 400 | Validation |
| TC12 | Empty body — all fields missing → 400 | Validation |

---

## 🛠️ cURL Examples

**Analyze a lead:**
```bash
curl -X POST http://localhost:3000/crm/analyze-lead \
  -H "Content-Type: application/json" \
  -d '{
    "name": "James Hooper",
    "company": "OldGuard Manufacturing",
    "notes": "James was referred but said he has no budget this year and is happy with his current vendor."
  }'
```

**Health check:**
```bash
curl http://localhost:3000/health
```

---

## Project Structure

```
ai-crm-assistant/
│   ├── server.py        # Flask app + /crm/analyze-lead endpoint
│   └── llm_service.py   # Gemini API integration + output validation
│   └── test_crm.py      # 12 test cases (stdlib only, no pytest needed)
├── .env.example         # Environment variable template
├── requirements.txt     # pip dependencies
└── README.md
```

---

##  Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Your Google Gemini API key |
| `PORT` | ❌ | `3000` | Server port |
| `GEMINI_MODEL` | ❌ | `gemini-2.5-flash` | Gemini model to use |

---

##  Development

```bash
# Auto-reload on file changes (install watchdog first)
pip install flask[async] watchdog
flask --app src/server run --debug --port 3000
```

---

##  Design Decisions

- **Single LLM call**: All three outputs are generated together in one Gemini API request — minimal latency and cost.
- **JSON-only output**: The system instruction tells Gemini to return raw JSON with no markdown, ensuring reliable parsing.
- **Validation before LLM**: Input is validated before hitting the API to avoid wasting quota on bad data.
- **Output validation**: The LLM response is checked for required fields and valid enum values before being returned.
- **No third-party test framework**: Tests use Python stdlib (`urllib`, `json`) so there are zero extra dependencies.

---

##  Requirements

- Python ≥ 3.10
- A Google Gemini API key (free tier available)
