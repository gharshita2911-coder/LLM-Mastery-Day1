"""
knowledge_base.py
-----------------
Defines all 8 helpdesk categories, their keyword triggers for plain-English
matching, and the ordered troubleshooting steps shown to the user one-by-one.

Structure of each entry:
    {
        "display_name": str,          # shown in menus and emails
        "keywords":     list[str],    # used for plain-text keyword matching
        "urgent":       bool,         # True → escalation email marked URGENT
        "private_only": bool,         # True → sensitive reply sent via DM only
        "steps":        list[str],    # shown one at a time (Yes/No/Skip)
    }
"""

CATEGORIES: dict[str, dict] = {

    # ── 1. Account & Access ────────────────────────────────────────────────────
    "account_access": {
        "display_name": "Account & Access",
        "keywords": [
            "password", "reset", "locked", "lock", "mfa", "authenticator",
            "two factor", "2fa", "account", "login", "sign in", "access",
            "permission", "role", "privilege", "disabled account",
        ],
        "urgent": False,
        "private_only": False,
        "steps": [
            "Open a private / incognito browser window and navigate to "
            "https://aka.ms/sspr — this is Microsoft's self-service password reset portal.",
            "Click 'Forgot my password', enter your corporate email address, "
            "and complete the identity verification (Authenticator app or backup email).",
            "If your account is locked, wait 15 minutes and try again — "
            "Azure AD auto-unlocks after the lockout period.",
            "For MFA issues, open the Microsoft Authenticator app → "
            "tap your account → tap 'Refresh'. If the app is missing, "
            "re-enroll at https://aka.ms/mfasetup.",
            "For permission or access requests, ask your line manager to raise "
            "a request in the IT Service Portal with the resource name and business justification.",
        ],
    },

    # ── 2. Microsoft 365 ───────────────────────────────────────────────────────
    "microsoft_365": {
        "display_name": "Microsoft 365",
        "keywords": [
            "teams", "outlook", "email", "sharepoint", "onedrive", "word",
            "excel", "powerpoint", "office", "365", "m365", "calendar",
            "meeting", "sync", "not loading", "cannot open",
        ],
        "urgent": False,
        "private_only": False,
        "steps": [
            "Sign out of all Microsoft 365 apps, then sign back in with your "
            "corporate credentials to refresh your authentication token.",
            "Clear the application cache: close the app → hold Shift while "
            "reopening it (Teams) or navigate to "
            "AppData\\Local\\Microsoft\\Office\\16.0\\OfficeFileCache and delete its contents.",
            "Check the Microsoft 365 Service Health dashboard at "
            "https://admin.microsoft.com — your admin can verify if there is a "
            "known service outage affecting your region.",
            "Run a quick repair: Control Panel → Programs → Microsoft 365 → "
            "Change → Quick Repair. This fixes corrupt local installation files.",
            "If OneDrive is not syncing, click the OneDrive tray icon → "
            "Settings → Account → Unlink this PC, then sign in again to "
            "re-establish the sync connection.",
        ],
    },

    # ── 3. Hardware & Peripherals ──────────────────────────────────────────────
    "hardware_peripherals": {
        "display_name": "Hardware & Peripherals",
        "keywords": [
            "monitor", "screen", "display", "dock", "docking", "docking station",
            "webcam", "camera", "microphone", "mic", "headset", "headphones",
            "printer", "print", "usb", "keyboard", "mouse", "peripheral",
            "not detected", "no sound", "audio",
        ],
        "urgent": False,
        "private_only": False,
        "steps": [
            "Disconnect the device, wait 10 seconds, and reconnect it. "
            "For USB peripherals, try a different USB port.",
            "Open Device Manager (Win + X → Device Manager) and look for "
            "any yellow warning icons. Right-click the device → Update Driver → "
            "Search automatically for drivers.",
            "For monitors or docking stations, try a different cable "
            "(DisplayPort, HDMI, or USB-C). Faulty cables are a very common cause.",
            "Restart the print spooler service: open Services.msc, find "
            "'Print Spooler', right-click → Restart. Then delete pending jobs "
            "from C:\\Windows\\System32\\spool\\PRINTERS.",
            "For webcams or microphones, go to Settings → Privacy → Camera / "
            "Microphone and ensure the app you're using has permission to access it.",
        ],
    },

    # ── 4. Connectivity ────────────────────────────────────────────────────────
    "connectivity": {
        "display_name": "Connectivity",
        "keywords": [
            "vpn", "wifi", "wi-fi", "internet", "network", "remote desktop",
            "rdp", "no connection", "slow internet", "disconnecting",
            "globalprotect", "anyconnect", "proxy", "firewall",
        ],
        "urgent": False,
        "private_only": True,   # WiFi passwords sent via DM only
        "steps": [
            "Run the Windows Network Troubleshooter: Settings → System → "
            "Troubleshoot → Internet Connections, and follow the on-screen steps.",
            "Forget and reconnect to the WiFi network: Settings → Network & "
            "Internet → Wi-Fi → Manage known networks → Remove the network, "
            "then reconnect and enter credentials.",
            "For VPN issues, close GlobalProtect / Cisco AnyConnect completely, "
            "restart the VPN service via Services.msc, then reopen and reconnect.",
            "Flush your DNS cache: open Command Prompt as Administrator and run "
            "'ipconfig /flushdns' followed by 'ipconfig /release' and 'ipconfig /renew'.",
            "For Remote Desktop issues, ensure the target machine is powered on "
            "and RDP is enabled: Settings → System → Remote Desktop → Enable.",
        ],
    },

    # ── 5. Software & Updates ─────────────────────────────────────────────────
    "software_updates": {
        "display_name": "Software & Updates",
        "keywords": [
            "install", "installation", "software", "update", "windows update",
            "crash", "crashing", "not opening", "freezing", "app", "application",
            "uninstall", "error", "stuck on update",
        ],
        "urgent": False,
        "private_only": False,
        "steps": [
            "Restart the application and try again. If it crashes on startup, "
            "run it as Administrator (right-click → Run as administrator).",
            "Check Windows Update: Settings → Windows Update → Check for updates. "
            "Install all pending updates and restart if prompted.",
            "Verify the application is on the approved software list. "
            "Request installation through the IT Service Portal — "
            "direct installs may be blocked by device policy.",
            "Repair or reinstall the application: Control Panel → Programs → "
            "find the app → Change → Repair. If that fails, uninstall and "
            "reinstall from the company software portal.",
            "Check application logs in Event Viewer (Win + X → Event Viewer → "
            "Windows Logs → Application) for the specific error code and "
            "share it with IT if escalating.",
        ],
    },

    # ── 6. Performance ────────────────────────────────────────────────────────
    "performance": {
        "display_name": "Performance",
        "keywords": [
            "slow", "sluggish", "laggy", "freeze", "hanging", "disk space",
            "storage", "full disk", "startup", "boot", "takes long", "speed",
            "memory", "ram", "cpu", "high cpu", "fan noise",
        ],
        "urgent": False,
        "private_only": False,
        "steps": [
            "Open Task Manager (Ctrl + Shift + Esc) → Processes tab. "
            "Sort by CPU or Memory. If any unexpected process is consuming "
            "over 80%, right-click it and select End Task.",
            "Free up disk space: open Settings → System → Storage → "
            "Temporary files, tick all temporary/cache categories, and click "
            "'Remove files'. Aim to keep at least 10 GB free.",
            "Disable startup programs that slow boot time: "
            "Task Manager → Startup tab → right-click high-impact items → Disable.",
            "Run Disk Cleanup as Administrator and also run "
            "'Optimize Drives' (search in Start menu) to defragment or "
            "TRIM your drive.",
            "If the issue persists after a full restart, note the laptop model "
            "and age — hardware may be due for an upgrade. Provide your asset ID "
            "so IT can check the refresh cycle.",
        ],
    },

    # ── 7. Security ───────────────────────────────────────────────────────────
    "security": {
        "display_name": "Security",
        "keywords": [
            "phishing", "suspicious", "malware", "virus", "hack", "hacked",
            "compromised", "lost", "stolen", "device stolen", "laptop stolen",
            "ransomware", "unusual activity", "scam", "fraud", "data breach",
        ],
        "urgent": True,    # always escalate as URGENT
        "private_only": False,
        "steps": [
            "DO NOT click any links or open attachments in suspicious emails. "
            "Forward the email as an attachment to your IT security team at "
            "security@yourcompany.com, then delete it from your inbox.",
            "If you believe your account is compromised, change your password "
            "IMMEDIATELY at https://aka.ms/sspr and revoke all active sessions "
            "via https://myaccount.microsoft.com → Security → Sign-out everywhere.",
            "For a lost or stolen device, notify IT immediately so the device "
            "can be remotely wiped via Intune MDM. Do NOT wait.",
            "Run a full Windows Defender scan: Windows Security → "
            "Virus & Threat Protection → Full Scan.",
            "Disconnect from the corporate network (WiFi and VPN) if you "
            "suspect active malware or ransomware, to prevent lateral spread.",
        ],
    },

    # ── 8. Equipment Requests ─────────────────────────────────────────────────
    "equipment_requests": {
        "display_name": "Equipment Requests",
        "keywords": [
            "new laptop", "replacement", "hardware request", "new starter",
            "onboarding kit", "equipment", "request laptop", "new device",
            "setup", "starter kit", "new joiners",
        ],
        "urgent": False,
        "private_only": False,
        "steps": [
            "Log a formal equipment request in the IT Service Portal "
            "(link in your company intranet) with: your full name, department, "
            "manager name, and justification.",
            "For new starters, the hiring manager should submit the onboarding "
            "kit request at least 5 business days before the start date to "
            "ensure timely delivery.",
            "For replacement hardware, confirm whether your device is in- or "
            "out-of-warranty by providing the asset tag (usually a sticker on "
            "the bottom of the laptop).",
            "IT will review the request and confirm the expected delivery date "
            "via email within 2 business days.",
        ],
    },
}


# ── Helper utilities ──────────────────────────────────────────────────────────

def get_category_by_keyword(text: str) -> str | None:
    """
    Scan user's free-text message for keywords and return the best-matching
    category key. Returns None if no match is found.
    """
    text_lower = text.lower()
    best_match: str | None = None
    best_count: int = 0

    for category_key, data in CATEGORIES.items():
        count = sum(1 for kw in data["keywords"] if kw in text_lower)
        if count > best_count:
            best_count = count
            best_match = category_key

    return best_match if best_count > 0 else None


def get_menu_text() -> str:
    """Return a numbered plaintext menu of all categories."""
    lines = ["Please choose a category or describe your issue:\n"]
    for i, (key, data) in enumerate(CATEGORIES.items(), start=1):
        lines.append(f"{i}. {data['display_name']}")
    lines.append("\nType the number or describe your issue in plain English.")
    return "\n".join(lines)


def get_category_by_number(number: str) -> str | None:
    """Map a menu number (1–8) to a category key."""
    try:
        idx = int(number.strip()) - 1
        keys = list(CATEGORIES.keys())
        if 0 <= idx < len(keys):
            return keys[idx]
    except ValueError:
        pass
    return None
