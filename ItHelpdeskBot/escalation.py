"""
escalation.py
-------------
Handles sending escalation emails to the IT team when troubleshooting steps
are exhausted or a security incident is reported.

Two sending methods are supported:
  1. SMTP (default)       — uses smtp.gmsil.com with STARTTLS
  2. Microsoft Graph API  — set USE_GRAPH_EMAIL=true in config for this path

The correct method is selected automatically based on config.USE_GRAPH_EMAIL.
"""

import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import DefaultConfig

logger = logging.getLogger(__name__)
CONFIG = DefaultConfig()


# ── Public entry point ────────────────────────────────────────────────────────

async def send_escalation_email(
    user_name: str,
    user_email: str,
    category_display: str,
    steps_tried: list[str],
    asset_id: str,
    urgent: bool = False,
) -> bool:
    """
    Build and send an escalation email.

    Parameters
    ----------
    user_name       : Display name of the Teams user
    user_email      : Email address of the Teams user
    category_display: Human-readable category name (from knowledge_base)
    steps_tried     : List of troubleshooting steps already attempted
    asset_id        : Laptop / asset tag provided by the user
    urgent          : True → subject prefixed with [URGENT], high-priority headers set

    Returns
    -------
    True on success, False on failure (error is logged, not raised).
    """
    subject, html_body, plain_body = _build_email_content(
        user_name, user_email, category_display,
        steps_tried, asset_id, urgent
    )

    if CONFIG.USE_GRAPH_EMAIL:
        return await _send_via_graph(subject, html_body)
    else:
        return _send_via_smtp(subject, html_body, plain_body)


# ── Email content builder ─────────────────────────────────────────────────────

def _build_email_content(
    user_name: str,
    user_email: str,
    category: str,
    steps_tried: list[str],
    asset_id: str,
    urgent: bool,
) -> tuple[str, str, str]:
    """Return (subject, html_body, plain_body)."""

    priority_label = "🔴 URGENT" if urgent else "🟡 Normal"
    priority_tag = "[URGENT]" if urgent else "[Helpdesk]"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    subject = f"{priority_tag} IT Escalation – {category} – {user_name}"

    # Numbered list of steps already tried
    steps_html = "".join(
        f"<li style='margin-bottom:6px'>{step}</li>"
        for step in steps_tried
    ) if steps_tried else "<li><em>No steps recorded</em></li>"

    steps_plain = "\n".join(
        f"  {i}. {step}" for i, step in enumerate(steps_tried, 1)
    ) if steps_tried else "  None recorded"

    html_body = f"""
    <html><body style="font-family: Segoe UI, Arial, sans-serif; font-size:14px; color:#1f1f1f;">
      <div style="max-width:640px; margin:0 auto; border:1px solid #e0e0e0;
                  border-radius:8px; overflow:hidden;">

        <!-- Header -->
        <div style="background:{'#c00000' if urgent else '#0078d4'};
                    padding:16px 24px; color:#ffffff;">
          <h2 style="margin:0; font-size:18px;">
            {'🔴 URGENT — ' if urgent else ''}IT Helpdesk Escalation
          </h2>
          <p style="margin:4px 0 0; font-size:12px; opacity:0.85;">
            Submitted: {timestamp}
          </p>
        </div>

        <!-- Details -->
        <div style="padding:24px;">
          <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr>
              <td style="padding:8px 0; color:#555; width:140px;">User</td>
              <td style="padding:8px 0; font-weight:600;">{user_name}</td>
            </tr>
            <tr>
              <td style="padding:8px 0; color:#555;">Email</td>
              <td style="padding:8px 0;">
                <a href="mailto:{user_email}" style="color:#0078d4;">{user_email}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 0; color:#555;">Category</td>
              <td style="padding:8px 0;">{category}</td>
            </tr>
            <tr>
              <td style="padding:8px 0; color:#555;">Asset / Laptop ID</td>
              <td style="padding:8px 0; font-family:monospace;">{asset_id}</td>
            </tr>
            <tr>
              <td style="padding:8px 0; color:#555;">Priority</td>
              <td style="padding:8px 0;">{priority_label}</td>
            </tr>
          </table>

          <hr style="border:none; border-top:1px solid #e0e0e0; margin:16px 0;">

          <h3 style="font-size:14px; margin-bottom:8px; color:#333;">
            Troubleshooting steps already attempted:
          </h3>
          <ol style="margin:0; padding-left:20px; color:#333; line-height:1.7;">
            {steps_html}
          </ol>

          <div style="margin-top:24px; padding:12px 16px;
                      background:#fff4ce; border-left:4px solid #f7a800;
                      border-radius:4px; font-size:13px;">
            {'⚠️ This is a <strong>security incident</strong>. Please treat as highest priority.'
              if urgent else
              'All listed steps were attempted by the user without resolution.'}
          </div>
        </div>

        <!-- Footer -->
        <div style="background:#f4f4f4; padding:12px 24px;
                    font-size:12px; color:#888; text-align:center;">
          Auto-generated by IT Helpdesk Bot · Microsoft Teams
        </div>
      </div>
    </body></html>
    """

    plain_body = f"""IT HELPDESK ESCALATION
{'=' * 40}
Submitted : {timestamp}
User      : {user_name} <{user_email}>
Category  : {category}
Asset ID  : {asset_id}
Priority  : {priority_label}

Steps already attempted:
{steps_plain}

{'*** SECURITY INCIDENT — TREAT AS HIGHEST PRIORITY ***' if urgent else ''}

-- Auto-generated by IT Helpdesk Bot (Microsoft Teams)
"""

    return subject, html_body, plain_body


# ── SMTP sender ───────────────────────────────────────────────────────────────

def _send_via_smtp(subject: str, html_body: str, plain_body: str) -> bool:
    """Send email via SMTP with STARTTLS (works with Gmail and Office 365)."""

    # ── Log which config is being used so you can spot mismatches immediately ─
    logger.info(
        "SMTP config → host=%s  port=%s  user=%s  to=%s",
        CONFIG.SMTP_HOST, CONFIG.SMTP_PORT, CONFIG.SMTP_USER, CONFIG.IT_TEAM_EMAIL,
    )

    # ── Guard: fail fast with a clear message if any value is missing ─────────
    if not CONFIG.SMTP_USER:
        logger.error("❌ SMTP_USER is empty — add it to your .env file.")
        return False
    if not CONFIG.SMTP_PASSWORD:
        logger.error("❌ SMTP_PASSWORD is empty — add your App Password to .env.")
        return False
    if not CONFIG.IT_TEAM_EMAIL:
        logger.error("❌ IT_TEAM_EMAIL is empty — add the recipient address to .env.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = CONFIG.SMTP_USER
    msg["To"]      = CONFIG.IT_TEAM_EMAIL
    msg["X-Priority"] = "1"

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    try:
        with smtplib.SMTP(CONFIG.SMTP_HOST, CONFIG.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(CONFIG.SMTP_USER, CONFIG.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("✅ Escalation email sent to %s via SMTP.", CONFIG.IT_TEAM_EMAIL)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("❌ SMTP login failed: %s", exc)
        logger.error(
            "Make sure SMTP_PASSWORD is a Gmail App Password (16 chars), "
            "not your normal Google account password. "
            "Generate one at: https://myaccount.google.com → Security → App passwords"
        )
    except smtplib.SMTPConnectError as exc:
        logger.error("❌ Cannot connect to %s:%s — %s", CONFIG.SMTP_HOST, CONFIG.SMTP_PORT, exc)
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("❌ Recipient refused: %s", exc)
    except smtplib.SMTPException as exc:
        logger.error("❌ SMTP error: %s", exc)
    except OSError as exc:
        logger.error("❌ Network error: %s", exc)
    return False


# ── Microsoft Graph API sender (optional) ─────────────────────────────────────

async def _send_via_graph(subject: str, html_body: str) -> bool:
    """
    Send email using Microsoft Graph API (client credentials flow).

    Requires:
      GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET in config.
      The app registration needs Mail.Send application permission.
    """
    try:
        import aiohttp  # already a project dependency via botbuilder
    except ImportError:
        logger.error("aiohttp not available for Graph API email sending.")
        return False

    if not all([CONFIG.GRAPH_TENANT_ID, CONFIG.GRAPH_CLIENT_ID,
                CONFIG.GRAPH_CLIENT_SECRET, CONFIG.SMTP_USER]):
        logger.error("Graph API credentials are incomplete.")
        return False

    # Step 1: Obtain an access token via client credentials
    token_url = (
        f"https://login.microsoftonline.com/{CONFIG.GRAPH_TENANT_ID}/oauth2/v2.0/token"
    )
    token_data = {
        "grant_type": "client_credentials",
        "client_id": CONFIG.GRAPH_CLIENT_ID,
        "client_secret": CONFIG.GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }

    async with aiohttp.ClientSession() as session:
        # Fetch token
        async with session.post(token_url, data=token_data) as resp:
            if resp.status != 200:
                logger.error("Failed to obtain Graph API token: %s", await resp.text())
                return False
            token_json = await resp.json()
            access_token = token_json.get("access_token")

        # Step 2: Send the email via /sendMail
        send_url = (
            f"https://graph.microsoft.com/v1.0/users/{CONFIG.SMTP_USER}/sendMail"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [
                    {"emailAddress": {"address": CONFIG.IT_TEAM_EMAIL}}
                ],
                "importance": "high",
            },
            "saveToSentItems": "false",
        }

        async with session.post(send_url, headers=headers, json=payload) as resp:
            if resp.status == 202:
                logger.info("Escalation email sent via Microsoft Graph API.")
                return True
            else:
                logger.error("Graph API sendMail failed: %s", await resp.text())
                return False