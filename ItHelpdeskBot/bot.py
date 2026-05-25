"""
bot.py — ITHelpdeskBot with Adaptive Card UI
Uses Adaptive Cards for: main menu, step-by-step flow, asset ID input, and confirmations.
Plain text fallback commands (menu / help / restart) still work via keyword detection.
"""

import logging
from botbuilder.core import ActivityHandler, TurnContext, ConversationState, MessageFactory
from botbuilder.schema import Activity, ActivityTypes

from knowledge_base import CATEGORIES
from escalation import send_escalation_email
from cards import (
    make_menu_card,
    make_step_card,
    make_asset_id_card,
    make_resolved_card,
    make_escalation_card,
)

logger = logging.getLogger(__name__)

CATEGORY_KEYS = [
    "account_access",
    "microsoft_365",
    "hardware_peripherals",
    "connectivity",
    "software_updates",
    "performance",
    "security",
    "equipment_requests",
]

GLOBAL_RESET_TRIGGERS = {"menu", "help", "start", "hi", "hello", "restart"}


def _get_state(conv_data: dict) -> dict:
    if "state" not in conv_data:
        conv_data["state"] = {}
    return conv_data["state"]


def _reset_state(state: dict) -> None:
    state.clear()


def _extract_text(turn_context: TurnContext) -> tuple[str, dict]:
    """
    Return (normalised_text, card_value) from the activity.

    Card button clicks arrive with activity.text = None and a payload in
    activity.value like {"value": "4", "msteams": {...}}.
    Typed messages arrive with activity.text set and activity.value = None.

    We look for text in this priority order:
      1. activity.value["msteams"]["text"]   ← Teams messageBack text
      2. activity.value["value"]             ← our explicit value field
      3. activity.text                       ← plain typed message
    """
    raw_text = (turn_context.activity.text or "").strip()
    card_value = turn_context.activity.value  # dict or None

    if card_value and isinstance(card_value, dict):
        # Try msteams.text first (Teams), then our "value" key, then raw text
        ms = card_value.get("msteams") or {}
        text = (
            ms.get("text")
            or card_value.get("value")
            or raw_text
        ).strip().lower()
    else:
        text = raw_text.lower()

    return text, card_value


class ITHelpdeskBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self._conv_state = conversation_state
        self._conv_data_accessor = conversation_state.create_property("ConversationData")

    # ──────────────────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────────────────

    async def on_message_activity(self, turn_context: TurnContext):
        conv_data: dict = await self._conv_data_accessor.get(turn_context, dict)
        state = _get_state(conv_data)

        user_name = turn_context.activity.from_property.name or "there"
        channel = turn_context.activity.channel_id or ""

        # Safe bool — emulator sends None, not False
        is_group = bool(turn_context.activity.conversation.is_group)

        text, card_value = _extract_text(turn_context)

        logger.info(
            "Turn: user=%s channel=%s group=%s text=%r card_value=%r",
            user_name, channel, is_group, text, card_value,
        )

        # ── Global reset ─────────────────────────────────────────────────────
        if text in GLOBAL_RESET_TRIGGERS:
            _reset_state(state)
            await self._send_menu(turn_context, user_name)
            await self._conv_state.save_changes(turn_context)
            return

        # ── Route ────────────────────────────────────────────────────────────
        if state.get("awaiting_asset_id"):
            await self._handle_asset_id(turn_context, state, text, card_value, user_name)

        elif state.get("category_key"):
            await self._handle_step_reply(turn_context, state, text, user_name)

        else:
            await self._handle_category_selection(turn_context, state, text, is_group)

        await self._conv_state.save_changes(turn_context)

    # ──────────────────────────────────────────────────────────────────────────
    # Menu
    # ──────────────────────────────────────────────────────────────────────────

    async def _send_menu(self, turn_context: TurnContext, user_name: str):
        await turn_context.send_activity(
            MessageFactory.text(f"👋 Hi **{user_name}**! I'm the IT Helpdesk Bot.")
        )
        await turn_context.send_activity(MessageFactory.attachment(make_menu_card()))

    # ──────────────────────────────────────────────────────────────────────────
    # Category selection
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_category_selection(
        self, turn_context: TurnContext, state: dict, text: str, is_group: bool
    ):
        category_key = self._resolve_category(text)

        if not category_key:
            await turn_context.send_activity(
                MessageFactory.text("I didn't quite catch that. Here's what I can help with:")
            )
            await turn_context.send_activity(MessageFactory.attachment(make_menu_card()))
            return

        category = CATEGORIES[category_key]

        # Connectivity → DM only in real group channels (not emulator)
        if category.get("private_only") and is_group:
            await turn_context.send_activity(
                MessageFactory.text(
                    "🔒 For security, connectivity and VPN topics should be discussed in a "
                    "**private chat**. Please message me directly and I'll help you there."
                )
            )
            return

        state["category_key"] = category_key
        state["step_index"] = 0
        state["steps_tried"] = []

        logger.info("Category started: %s (%d steps)", category_key, len(category["steps"]))
        await self._send_step(turn_context, state)

    # ──────────────────────────────────────────────────────────────────────────
    # Step reply
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_step_reply(
        self, turn_context: TurnContext, state: dict, text: str, user_name: str
    ):
        if text in ("yes", "y", "resolved", "fixed", "done"):
            _reset_state(state)
            await turn_context.send_activity(
                MessageFactory.attachment(make_resolved_card(user_name))
            )
            return

        if text in ("no", "n", "skip", "next", "still not resolved"):
            category_key = state["category_key"]
            steps = CATEGORIES[category_key]["steps"]
            current_index = state["step_index"]

            state["steps_tried"].append(current_index + 1)
            state["step_index"] = current_index + 1

            if state["step_index"] < len(steps):
                await self._send_step(turn_context, state)
            else:
                state["awaiting_asset_id"] = True
                await turn_context.send_activity(
                    MessageFactory.attachment(make_asset_id_card())
                )
            return

        await turn_context.send_activity(
            MessageFactory.text("Please use the **Yes**, **No**, or **Skip** buttons on the card above.")
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Asset ID + escalation
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_asset_id(
        self,
        turn_context: TurnContext,
        state: dict,
        text: str,
        card_value: dict,
        user_name: str,
    ):
        asset_id = ""
        if card_value and isinstance(card_value, dict):
            asset_id = (card_value.get("asset_id") or "").strip()

        if not asset_id and text not in ("skip", "asset_submit", ""):
            asset_id = text

        category_key = state["category_key"]
        category = CATEGORIES[category_key]
        steps_tried = state.get("steps_tried", [])
        urgent = category.get("urgent", False)
        user_email = getattr(turn_context.activity.from_property, "aad_object_id", None) or ""

        all_steps = category["steps"]
        tried_descriptions = [
            f"{n}. {all_steps[n - 1]}" for n in steps_tried if 1 <= n <= len(all_steps)
        ]

        logger.info(
            "Escalating: category=%s asset_id=%r urgent=%s tried_steps=%s",
            category_key, asset_id, urgent, steps_tried,
        )

        try:
            await send_escalation_email(
                user_name=user_name,
                user_email=user_email,
                category_display=category["display_name"],
                asset_id=asset_id,
                steps_tried=tried_descriptions,
                urgent=urgent,
            )
            email_ok = True
        except Exception as exc:
            logger.error("Escalation email failed: %s", exc)
            email_ok = False

        _reset_state(state)

        if email_ok:
            await turn_context.send_activity(
                MessageFactory.attachment(
                    make_escalation_card(
                        category_name=category["display_name"],
                        asset_id=asset_id,
                        urgent=urgent,
                    )
                )
            )
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "⚠️ I wasn't able to send the escalation email right now. "
                    "Please contact the IT team directly. Type **menu** to start again."
                )
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Send step card
    # ──────────────────────────────────────────────────────────────────────────

    async def _send_step(self, turn_context: TurnContext, state: dict):
        category_key = state["category_key"]
        category = CATEGORIES[category_key]
        steps = category["steps"]
        step_index = state["step_index"]
        total = len(steps)

        logger.info("Sending step %d/%d for category %s", step_index + 1, total, category_key)

        await turn_context.send_activity(
            MessageFactory.attachment(
                make_step_card(
                    category_name=category["display_name"],
                    step_number=step_index + 1,
                    total_steps=total,
                    step_text=steps[step_index],
                    is_last=(step_index == total - 1),
                )
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Category resolver
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_category(text: str) -> str | None:
        if text.strip() in [str(i) for i in range(1, 9)]:
            return CATEGORY_KEYS[int(text.strip()) - 1]

        for key, category in CATEGORIES.items():
            for keyword in category.get("keywords", []):
                if keyword.lower() in text:
                    return key

        return None

    # ──────────────────────────────────────────────────────────────────────────
    # New conversation
    # ──────────────────────────────────────────────────────────────────────────

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                user_name = member.name or "there"
                conv_data: dict = await self._conv_data_accessor.get(turn_context, dict)
                state = _get_state(conv_data)
                _reset_state(state)
                await self._send_menu(turn_context, user_name)
                await self._conv_state.save_changes(turn_context)