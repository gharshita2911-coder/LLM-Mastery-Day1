"""
Test Queries — 20 Diverse Questions for RAG Phase 2 E2E Testing
================================================================
Covers all knowledge base categories: passwords, network, software,
security, IT support, hardware, onboarding, backup.
"""

TEST_QUERIES: list[str] = [
    # ── Password & Account ────────────────────────────────────────────────
    "What are the requirements for creating a strong password?",
    "How do I reset my forgotten password?",
    "How do I enable multi-factor authentication on my account?",
    "How can I update my profile information?",
    # ── Network & Connectivity ────────────────────────────────────────────
    "How do I connect to the corporate VPN?",
    "What is the Wi-Fi SSID and how do I connect to it?",
    "What should I do if my internet is slow?",
    # ── Software & Applications ───────────────────────────────────────────
    "What email client does the company use and what is the mailbox quota?",
    "What is the official team communication platform?",
    "How can I get new software installed on my computer?",
    # ── Security & Compliance ─────────────────────────────────────────────
    "How do I report a phishing email?",
    "Where can I store company data safely?",
    "What is the screen lock policy?",
    # ── IT Support & Escalation ───────────────────────────────────────────
    "What are the IT helpdesk hours and how can I contact them?",
    "What are the incident severity levels for IT issues?",
    "How do I report a critical system outage?",
    # ── Hardware & Devices ────────────────────────────────────────────────
    "What laptop models are available through the company?",
    "How do I request a hardware repair?",
    # ── Onboarding & Offboarding ──────────────────────────────────────────
    "What happens during new employee IT onboarding?",
    # ── Backup & Recovery ─────────────────────────────────────────────────
    "How do I recover a deleted file from OneDrive?",
]

assert len(TEST_QUERIES) == 20, "Must be exactly 20 test queries"
