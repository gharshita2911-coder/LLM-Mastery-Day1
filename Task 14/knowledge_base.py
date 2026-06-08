"""
Knowledge Base — Chunk Storage & Retrieval
===========================================
Stores documents as chunked entries. Each chunk has a unique chunkId,
category, and text content. Provides cosine-similarity retrieval via
a lightweight TF-IDF-like scoring mechanism (no external vector DB needed).
"""

import math
import re
from collections import Counter


# ── Document Chunks ────────────────────────────────────────────────────────────

_DOCUMENTS: list[dict] = [
    # ── Password & Account Management ─────────────────────────────────────
    {
        "chunkId": "chunk_001",
        "category": "Password & Account",
        "text": "Password requirements for creating a strong password: Passwords must be "
                "at least 12 characters long and include uppercase, lowercase, digit, "
                "and special character. Accounts lock after 5 failed attempts for "
                "30 minutes. A strong password is hard to guess and meets all "
                "complexity requirements.",
    },
    {
        "chunkId": "chunk_002",
        "category": "Password & Account",
        "text": "To reset a forgotten password, go to the login page and click "
                "'Forgot Password'. An email with a reset link is sent to the "
                "registered email address. The link expires in 24 hours.",
    },
    {
        "chunkId": "chunk_003",
        "category": "Password & Account",
        "text": "Multi-factor authentication (MFA) can be enabled under "
                "Account Settings > Security. Supported methods: authenticator "
                "app, SMS code, or hardware security key.",
    },
    {
        "chunkId": "chunk_004",
        "category": "Password & Account",
        "text": "To update your profile information, navigate to Account "
                "Settings > Profile. You can change your name, email address, "
                "phone number, and profile picture. Changes take effect immediately.",
    },
    # ── Network & Connectivity ────────────────────────────────────────────
    {
        "chunkId": "chunk_005",
        "category": "Network & Connectivity",
        "text": "The corporate VPN supports OpenVPN and WireGuard protocols. "
                "Connection requires a valid client certificate and "
                "company-issued credentials. Download client config from the IT portal.",
    },
    {
        "chunkId": "chunk_006",
        "category": "Network & Connectivity",
        "text": "Wi-Fi SSID: 'Corp-Net' with WPA2-Enterprise encryption. "
                "Use your employee badge number and network password to connect. "
                "Guest network SSID: 'Corp-Guest' with daily passcode from reception.",
    },
    {
        "chunkId": "chunk_007",
        "category": "Network & Connectivity",
        "text": "If you experience slow internet, first check your connection "
                "speed at speedtest.company.internal. Then close bandwidth-heavy "
                "applications. If issues persist, restart your router and contact IT.",
    },
    # ── Software & Applications ────────────────────────────────────────────
    {
        "chunkId": "chunk_008",
        "category": "Software & Applications",
        "text": "The approved email client is Microsoft Outlook. Company email "
                "can also be accessed via Outlook Web App (OWA) at "
                "mail.company.internal. Default mailbox quota is 50 GB.",
    },
    {
        "chunkId": "chunk_009",
        "category": "Software & Applications",
        "text": "Slack is the official team communication platform. Channels are "
                "organized by department. Use @here for urgent messages and "
                "@channel sparingly. Do not share sensitive data in public channels.",
    },
    {
        "chunkId": "chunk_010",
        "category": "Software & Applications",
        "text": "Available IDE options: VS Code (recommended), IntelliJ IDEA, "
                "and PyCharm. Extensions can be installed via the internal "
                "extension marketplace. All IDEs are configured with company "
                "coding standards.",
    },
    {
        "chunkId": "chunk_011",
        "category": "Software & Applications",
        "text": "To install company-approved software, use the Software Center "
                "app on your managed device. Request new software via the IT "
                "helpdesk portal at helpdesk.company.internal.",
    },
    # ── Security & Compliance ──────────────────────────────────────────────
    {
        "chunkId": "chunk_012",
        "category": "Security & Compliance",
        "text": "Report phishing emails immediately using the 'Report Phishing' "
                "button in Outlook. Do not click links or download attachments "
                "from suspicious emails. The security team reviews all reports.",
    },
    {
        "chunkId": "chunk_013",
        "category": "Security & Compliance",
        "text": "Company data must never be stored on personal devices or "
                "unapproved cloud services. Approved cloud storage: OneDrive "
                "for Business and SharePoint. All data at rest is AES-256 encrypted.",
    },
    {
        "chunkId": "chunk_014",
        "category": "Security & Compliance",
        "text": "Screen lock must activate after 15 minutes of inactivity. "
                "Employees must lock their workstation when leaving their desk. "
                "Violations are reported to the compliance team.",
    },
    # ── IT Support & Escalation ────────────────────────────────────────────
    {
        "chunkId": "chunk_015",
        "category": "IT Support & Escalation",
        "text": "IT helpdesk hours: Monday–Friday, 8 AM – 8 PM EST. "
                "Contact via phone (ext. 4357), email (helpdesk@company.internal), "
                "or the self-service portal. Priority response within 1 hour for P1 issues.",
    },
    {
        "chunkId": "chunk_016",
        "category": "IT Support & Escalation",
        "text": "Incident severity levels: P1 (Critical — system down), "
                "P2 (High — major feature broken, no workaround), "
                "P3 (Medium — partial impairment, workaround exists), "
                "P4 (Low — cosmetic or minor issue).",
    },
    {
        "chunkId": "chunk_017",
        "category": "IT Support & Escalation",
        "text": "For P1 and P2 incidents, call the IT hotline immediately. "
                "Do not rely on email or the portal for critical issues. "
                "The on-call engineer will respond within 15 minutes.",
    },
    # ── Hardware & Devices ─────────────────────────────────────────────────
    {
        "chunkId": "chunk_018",
        "category": "Hardware & Devices",
        "text": "Standard laptop models: Dell Latitude 5540 (Windows) and "
                "MacBook Pro 14-inch (macOS). Request hardware through the IT "
                "procurement portal with manager approval.",
    },
    {
        "chunkId": "chunk_019",
        "category": "Hardware & Devices",
        "text": "Printer setup: Connect to the corporate network, then run the "
                "printer installer from Software Center. Default printer naming: "
                "'Floor-Building-DeviceNumber'.",
    },
    {
        "chunkId": "chunk_020",
        "category": "Hardware & Devices",
        "text": "To request a hardware repair, log a ticket on the IT portal "
                "with the asset tag number. Replacement devices are issued "
                "within 2 business days for approved requests.",
    },
    # ── Onboarding & Offboarding ───────────────────────────────────────────
    {
        "chunkId": "chunk_021",
        "category": "Onboarding & Offboarding",
        "text": "New employee onboarding: IT provisions accounts within 48 "
                "hours of HR notification. Welcome kit includes laptop, "
                "monitor, keyboard, mouse, and company badge. "
                "Accounts are created for email, VPN, Slack, and internal tools.",
    },
    {
        "chunkId": "chunk_022",
        "category": "Onboarding & Offboarding",
        "text": "Offboarding process: Manager submits termination request in HR "
                "system. IT revokes all access within 2 hours. Laptop and badge "
                "must be returned to IT on the last working day.",
    },
    # ── Backup & Recovery ──────────────────────────────────────────────────
    {
        "chunkId": "chunk_023",
        "category": "Backup & Recovery",
        "text": "Automatic backups run daily at 2 AM for all company-managed "
                "devices. OneDrive files are synced continuously. "
                "Retention policy: 30 days for files, 90 days for databases.",
    },
    {
        "chunkId": "chunk_024",
        "category": "Backup & Recovery",
        "text": "To recover a deleted file from OneDrive, go to the OneDrive "
                "web interface, select 'Recycle Bin', locate the file, and "
                "click 'Restore'. Deleted items are retained for 30 days.",
    },
]


# ── Text utilities ────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple tokenisation — lower-cased words of 2+ alphabetic characters."""
    return re.findall(r"[a-z]{2,}", text.lower())


def _compute_tfidf_vector(
    tokens: list[str],
    idf: dict[str, float],
) -> Counter:
    """Compute TF-IDF vector as a Counter."""
    tf = Counter(tokens)
    max_freq = max(tf.values()) if tf else 1
    vec: Counter = Counter()
    for term, count in tf.items():
        vec[term] = (count / max_freq) * idf.get(term, 1.0)
    return vec


def _cosine_similarity(a: Counter, b: Counter) -> float:
    """Cosine similarity between two Counter vectors."""
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Global index (built once at import time) ──────────────────────────────────

_CORPUS_TOKENS: list[list[str]] = [_tokenize(d["text"]) for d in _DOCUMENTS]
_ALL_TOKENS: list[str] = [t for tokens in _CORPUS_TOKENS for t in tokens]
_TERM_FREQ: Counter = Counter(_ALL_TOKENS)
_NUM_DOCS: int = len(_DOCUMENTS)
_IDF: dict[str, float] = {
    term: math.log((_NUM_DOCS + 1) / (freq + 1)) + 1
    for term, freq in _TERM_FREQ.items()
}
_DOC_VECTORS: list[Counter] = [
    _compute_tfidf_vector(tokens, _IDF) for tokens in _CORPUS_TOKENS
]


# ── Public API ────────────────────────────────────────────────────────────────

def get_all_chunks() -> list[dict]:
    """Return the full list of document chunks."""
    return _DOCUMENTS.copy()


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the top_k most relevant chunks for the given query.

    Returns list of dicts with keys: chunkId, doc, score, category, text.
    """
    query_tokens = _tokenize(query)
    query_vec = _compute_tfidf_vector(query_tokens, _IDF)

    scored: list[tuple[float, int]] = []
    for i, doc_vec in enumerate(_DOC_VECTORS):
        sim = _cosine_similarity(query_vec, doc_vec)
        scored.append((sim, i))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[dict] = []
    for score, idx in scored[:top_k]:
        chunk = _DOCUMENTS[idx]
        results.append({
            "chunkId": chunk["chunkId"],
            "doc": chunk["text"][:80],
            "score": round(score, 4),
            "category": chunk["category"],
            "text": chunk["text"],
        })

    return results
