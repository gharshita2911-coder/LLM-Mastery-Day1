"""
app.py  (LOCAL / EMULATOR VERSION)
-----------------------------------
Runs the IT Helpdesk Bot locally against Bot Framework Emulator.

Run:
  python app.py

Then in Bot Framework Emulator:
  Bot URL  → http://localhost:3978/api/messages
  App ID   → (blank)
  Password → (blank)
"""

import logging
import sys

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    TurnContext,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity

from config import DefaultConfig
from bot import ITHelpdeskBot

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG = DefaultConfig()

# ── Adapter (no-auth for local emulator) ──────────────────────────────────────
SETTINGS = BotFrameworkAdapterSettings(
    app_id=CONFIG.APP_ID,
    app_password=CONFIG.APP_PASSWORD,
)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# ── State storage ──────────────────────────────────────────────────────────────
# MemoryStorage is fine for local dev / emulator.
# For production, swap MemoryStorage for CosmosDbPartitionedStorage.
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)

# ── Global error handler ───────────────────────────────────────────────────────
async def on_error(context: TurnContext, error: Exception):
    """Log the full traceback locally and send a friendly message to the emulator."""
    logger.exception("Unhandled exception in bot turn: %s", error)
    await context.send_activity(
        "⚠️ An unexpected error occurred. Please try again or type **menu** to restart."
    )

ADAPTER.on_turn_error = on_error

# ── Bot instance ───────────────────────────────────────────────────────────────
BOT = ITHelpdeskBot(conversation_state=CONVERSATION_STATE)

# ── Route handler ──────────────────────────────────────────────────────────────
async def messages(req: Request) -> Response:
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=415, text="Unsupported Media Type")

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)

    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=201)


# ── Health check ───────────────────────────────────────────────────────────────
async def health(req: Request) -> Response:
    return json_response({"status": "ok", "mode": "local-emulator"})


# ── App setup ──────────────────────────────────────────────────────────────────
APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  IT Helpdesk Bot — LOCAL / EMULATOR MODE")
    logger.info("  Listening on http://localhost:%d", CONFIG.PORT)
    logger.info("  Emulator URL  → http://localhost:%d/api/messages", CONFIG.PORT)
    logger.info("  App ID        → (leave blank in emulator)")
    logger.info("  App Password  → (leave blank in emulator)")
    logger.info("=" * 55)
    web.run_app(APP, host="localhost", port=CONFIG.PORT)