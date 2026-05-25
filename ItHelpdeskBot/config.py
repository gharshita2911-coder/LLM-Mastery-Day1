"""
config.py  (LOCAL / EMULATOR VERSION)
---------------------------------------
Reads configuration from environment variables.
For local development, values are loaded from a .env file via python-dotenv.

Local emulator rule:
  APP_ID and APP_PASSWORD must be empty strings ("") — NOT placeholder text.
  Any non-empty string causes BotFrameworkAdapter to attempt real token
  validation, which will fail against the emulator.
"""

import os
from dotenv import load_dotenv

# Load .env file (only takes effect locally; ignored on Azure where env vars
# are set directly in App Service Configuration)
load_dotenv()


class DefaultConfig:

    # ── Bot credentials ────────────────────────────────────────────────────────
    # Must be "" for local emulator. Fill in real values only for Azure.
    APP_ID: str = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD: str = os.environ.get("MicrosoftAppPassword", "")

    # ── Web server ─────────────────────────────────────────────────────────────
    PORT: int = int(os.environ.get("PORT", 3978))

    # ── Email escalation (SMTP) ────────────────────────────────────────────────
    SMTP_HOST: str = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER: str = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
    IT_TEAM_EMAIL: str = os.environ.get("IT_TEAM_EMAIL", "")

    # ── Microsoft Graph API email (optional alternative) ──────────────────────
    GRAPH_TENANT_ID: str = os.environ.get("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.environ.get("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.environ.get("GRAPH_CLIENT_SECRET", "")
    USE_GRAPH_EMAIL: bool = os.environ.get("USE_GRAPH_EMAIL", "false").lower() == "true"