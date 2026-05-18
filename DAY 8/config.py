"""
config.py – Shared settings, Gemini client pool, and data model
================================================================
Supports multiple API keys for fallback.
Add keys to your .env as:
    GEMINI_API_KEY=key1
    GEMINI_API_KEY_2=key2
    GEMINI_API_KEY_3=key3

If a key hits quota/rate-limit, the client pool automatically
rotates to the next available key. If all keys are exhausted,
a clear AllKeysExhaustedError is raised (pipeline catches it
and marks the ticket as failed — no crash).

Requires:
    pip install google-generativeai python-dotenv
"""

"""
config.py – Shared settings and Grok client
===========================================

Requires:
    pip install openai python-dotenv
"""
"""
config.py – Shared settings and Groq client
===========================================

Requires:
    pip install openai python-dotenv
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

MODEL = "llama-3.3-70b-versatile"
DB_PATH = "tickets.db"


# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise EnvironmentError(
        "Missing GROQ_API_KEY in .env file"
    )


# ---------------------------------------------------------------------------
# Groq Client
# ---------------------------------------------------------------------------

CLIENT = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


# ---------------------------------------------------------------------------
# Completion model
# ---------------------------------------------------------------------------

@dataclass
class Completion:

    prompt_token_count: Optional[int] = None
    candidates_token_count: Optional[int] = None
    total_token_count: Optional[int] = None

    def to_dict(self):

        return {
            "prompt_token_count": self.prompt_token_count,
            "candidates_token_count": self.candidates_token_count,
            "total_token_count": self.total_token_count,
        }


# ---------------------------------------------------------------------------
# TicketRecord
# ---------------------------------------------------------------------------

@dataclass
class TicketRecord:

    raw_text: str

    person: Optional[str] = None
    company: Optional[str] = None
    product: Optional[str] = None
    issue: Optional[str] = None

    category: Optional[str] = None

    summary: Optional[str] = None

    completion: Completion = field(
        default_factory=Completion
    )

    id: Optional[int] = None
    row_count: Optional[int] = None
    created_at: Optional[str] = None
    latency_ms: int = 0

    status: str = "success"
    error_step: Optional[str] = None
    error_msg: Optional[str] = None

    def to_dict(self):

        return {
            "id": self.id,
            "raw_text": self.raw_text,
            "person": self.person,
            "company": self.company,
            "product": self.product,
            "issue": self.issue,
            "category": self.category,
            "summary": self.summary,
            "completion": self.completion.to_dict(),
            "row_count": self.row_count,
            "created_at": self.created_at,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error_step": self.error_step,
            "error_msg": self.error_msg,
        }