"""
cards.py — Adaptive Card definitions for IT Helpdesk Bot
All cards use the Adaptive Card JSON format (schema 1.4) for maximum Teams + Emulator compatibility.
Returns botbuilder Attachment objects ready to attach to an Activity.
"""

from botbuilder.core import CardFactory
from botbuilder.schema import Attachment


# ──────────────────────────────────────────────────────────────────────────────
# CATEGORY MENU CARD
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_LABELS = [
    ("1", "🔐 Account & Access"),
    ("2", "📦 Microsoft 365"),
    ("3", "🖥️ Hardware & Peripherals"),
    ("4", "🌐 Connectivity / VPN"),
    ("5", "⬆️ Software & Updates"),
    ("6", "🐢 Performance Issues"),
    ("7", "🚨 Security Incident"),
    ("8", "💻 Equipment Request"),
]


def make_menu_card() -> Attachment:
    """
    Returns an Adaptive Card with 8 category buttons arranged in a 2-column grid.
    Each button sends a message with the number (e.g. "1") when tapped.
    """
    # Build button columns in pairs
    column_sets = []
    for i in range(0, len(CATEGORY_LABELS), 2):
        left_num, left_label = CATEGORY_LABELS[i]
        pair = [
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "ActionSet",
                        "actions": [
                            {
                                "type": "Action.Submit",
                                "title": left_label,
                                "data": {"msteams": {"type": "messageBack", "text": left_num}, "value": left_num},
                            }
                        ],
                    }
                ],
            }
        ]
        if i + 1 < len(CATEGORY_LABELS):
            right_num, right_label = CATEGORY_LABELS[i + 1]
            pair.append(
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.Submit",
                                    "title": right_label,
                                    "data": {"msteams": {"type": "messageBack", "text": right_num}, "value": right_num},
                                }
                            ],
                        }
                    ],
                }
            )
        else:
            # Odd item — fill right column with empty space
            pair.append({"type": "Column", "width": "stretch", "items": []})

        column_sets.append({"type": "ColumnSet", "columns": pair, "spacing": "Small"})

    card_body = [
        {
            "type": "TextBlock",
            "text": "🛠️ IT Helpdesk",
            "weight": "Bolder",
            "size": "Large",
            "color": "Accent",
        },
        {
            "type": "TextBlock",
            "text": "What can I help you with today? Choose a category:",
            "wrap": True,
            "spacing": "Small",
        },
        {"type": "Container", "spacing": "Medium", "items": column_sets},
    ]

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": card_body,
    }
    return CardFactory.adaptive_card(card)


# ──────────────────────────────────────────────────────────────────────────────
# TROUBLESHOOTING STEP CARD
# ──────────────────────────────────────────────────────────────────────────────

def make_step_card(
    category_name: str,
    step_number: int,
    total_steps: int,
    step_text: str,
    is_last: bool = False,
) -> Attachment:
    """
    Shows a single troubleshooting step with Yes / No / Skip buttons.
    When is_last=True, 'No' label changes to 'Still not resolved' for clarity.
    """
    no_label = "❌ Still not resolved" if is_last else "❌ No"

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": category_name,
                                "weight": "Bolder",
                                "color": "Accent",
                                "size": "Medium",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"Step {step_number} of {total_steps}",
                                "color": "Good",
                                "weight": "Bolder",
                                "horizontalAlignment": "Right",
                            }
                        ],
                    },
                ],
            },
            {
                "type": "TextBlock",
                "text": step_text,
                "wrap": True,
                "spacing": "Medium",
                "size": "Default",
            },
            {
                "type": "TextBlock",
                "text": "Did this resolve your issue?",
                "wrap": True,
                "spacing": "Medium",
                "isSubtle": True,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "✅ Yes, resolved!",
                "style": "positive",
                "data": {"msteams": {"type": "messageBack", "text": "yes"}, "value": "yes"},
            },
            {
                "type": "Action.Submit",
                "title": no_label,
                "style": "destructive",
                "data": {"msteams": {"type": "messageBack", "text": "no"}, "value": "no"},
            },
            {
                "type": "Action.Submit",
                "title": "⏭️ Skip",
                "data": {"msteams": {"type": "messageBack", "text": "skip"}, "value": "skip"},
            },
        ],
    }
    return CardFactory.adaptive_card(card)


# ──────────────────────────────────────────────────────────────────────────────
# ASSET ID INPUT CARD
# ──────────────────────────────────────────────────────────────────────────────

def make_asset_id_card() -> Attachment:
    """
    Shows a text input field for the user to enter their asset/device ID.
    On submit the bot receives the value in activity.value["asset_id"].
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "📋 Escalating to IT Team",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Warning",
            },
            {
                "type": "TextBlock",
                "text": (
                    "We'll escalate this to the IT team. "
                    "Please enter your **Asset / Device ID** below (e.g. LT-00123), "
                    "or tap **Skip** if you don't have it."
                ),
                "wrap": True,
                "spacing": "Small",
            },
            {
                "type": "Input.Text",
                "id": "asset_id",
                "placeholder": "e.g. LT-00123",
                "label": "Asset / Device ID",
                "isRequired": False,
                "maxLength": 50,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "📤 Submit & Escalate",
                "style": "positive",
                "data": {"msteams": {"type": "messageBack", "text": "asset_submit"}},
            },
            {
                "type": "Action.Submit",
                "title": "⏭️ Skip (no asset ID)",
                "data": {
                    "msteams": {"type": "messageBack", "text": "skip"},
                    "asset_id": "",
                },
            },
        ],
    }
    return CardFactory.adaptive_card(card)


# ──────────────────────────────────────────────────────────────────────────────
# CONFIRMATION / RESOLVED CARD
# ──────────────────────────────────────────────────────────────────────────────

def make_resolved_card(user_name: str) -> Attachment:
    """Shown when the user confirms the issue is resolved."""
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "✅ Great, glad that's sorted!",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Good",
            },
            {
                "type": "TextBlock",
                "text": f"Happy to help, {user_name}! Let me know if anything else comes up.",
                "wrap": True,
                "spacing": "Small",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🏠 Back to Main Menu",
                "data": {"msteams": {"type": "messageBack", "text": "menu"}, "value": "menu"},
            }
        ],
    }
    return CardFactory.adaptive_card(card)


# ──────────────────────────────────────────────────────────────────────────────
# ESCALATION CONFIRMATION CARD
# ──────────────────────────────────────────────────────────────────────────────

def make_escalation_card(category_name: str, asset_id: str, urgent: bool = False) -> Attachment:
    """
    Shown after the escalation email has been sent.
    """
    priority_text = "🚨 **URGENT**" if urgent else "Normal"
    asset_text = asset_id if asset_id else "Not provided"

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "📧 IT Team Notified",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Accent",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Category", "value": category_name},
                    {"title": "Asset / Device ID", "value": asset_text},
                    {"title": "Priority", "value": priority_text},
                ],
                "spacing": "Small",
            },
            {
                "type": "TextBlock",
                "text": "A member of the IT team will be in touch shortly. Is there anything else I can help with?",
                "wrap": True,
                "spacing": "Medium",
                "isSubtle": True,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🏠 Back to Main Menu",
                "data": {"msteams": {"type": "messageBack", "text": "menu"}, "value": "menu"},
            }
        ],
    }
    return CardFactory.adaptive_card(card)