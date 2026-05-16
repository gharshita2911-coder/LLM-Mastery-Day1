# tests/test_crm.py
# AI CRM Assistant — Test Suite (12 test cases)
# No third-party test libraries required — uses stdlib only.
#
# Usage:
#   python tests/test_crm.py              (server must be running: python src/server.py)
#   BASE_URL=http://localhost:5000 python tests/test_crm.py

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
VALID_SCORES = {"positive", "neutral", "negative"}

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def post(path: str, body: dict) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(path: str) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ── Assertion helpers ─────────────────────────────────────────────────────────

def assert_true(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def assert_analysis_shape(body: dict):
    assert_true(
        isinstance(body.get("summary"), str) and len(body["summary"]) > 20,
        f"summary must be a non-trivial string (got: {body.get('summary')!r})",
    )
    assert_true(
        isinstance(body.get("suggestedFollowUp"), str) and len(body["suggestedFollowUp"]) > 10,
        f"suggestedFollowUp must be a non-trivial string (got: {body.get('suggestedFollowUp')!r})",
    )
    assert_true(
        body.get("sentimentScore") in VALID_SCORES,
        f"sentimentScore must be positive/neutral/negative (got: {body.get('sentimentScore')!r})",
    )


# ── Test definitions ──────────────────────────────────────────────────────────

def tc01_positive_lead():
    """Strong interest, demo booked, budget approved → positive sentiment."""
    status, body = post("/crm/analyze-lead", {
        "name": "Priya Sharma",
        "company": "NovaTech Solutions",
        "notes": (
            "Priya attended our webinar and immediately booked a 1-on-1 demo. "
            "She said their current tool costs $20k/year and she'd like to switch by Q3. "
            "Budget already approved. Very excited."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    assert_true(
        body["sentimentScore"] == "positive",
        f"Expected positive, got {body['sentimentScore']!r}",
    )
    return body


def tc02_negative_lead():
    """Uninterested, no budget, happy with current vendor → negative sentiment."""
    status, body = post("/crm/analyze-lead", {
        "name": "James Hooper",
        "company": "OldGuard Manufacturing",
        "notes": (
            "James was referred but said he's happy with his current vendor "
            "and has no budget this fiscal year. Disinterested throughout the call. "
            "Did not ask any questions."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    assert_true(
        body["sentimentScore"] == "negative",
        f"Expected negative, got {body['sentimentScore']!r}",
    )
    return body


def tc03_neutral_lead():
    """Multi-vendor evaluation, no timeline → neutral sentiment."""
    status, body = post("/crm/analyze-lead", {
        "name": "Sarah Kim",
        "company": "Apex Consulting Group",
        "notes": (
            "Sarah is evaluating three vendors including us. She asked detailed "
            "questions about pricing and integrations. No decision timeline yet. "
            "Said she'll loop in their CTO next month."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    assert_true(body["sentimentScore"] in VALID_SCORES, "Sentiment must be valid")
    return body


def tc04_enterprise_lead():
    """Complex multi-team enterprise lead with compliance requirements."""
    status, body = post("/crm/analyze-lead", {
        "name": "Rajiv Menon",
        "company": "GlobalBank Corp",
        "notes": (
            "Rajiv leads digital transformation for a 12,000-person org. He has "
            "sign-off power but needs legal, compliance, and IT to approve any new SaaS. "
            "Compliance review takes 6-8 weeks. Very interested technically but procurement "
            "is lengthy. Asked for SOC 2 Type II report and GDPR addendum."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    assert_true(len(body["summary"]) > 50, "Enterprise summary should be detailed")
    return body


def tc05_urgent_lead():
    """Urgent deadline + approved budget → positive sentiment, time-bound follow-up."""
    status, body = post("/crm/analyze-lead", {
        "name": "Emily Chen",
        "company": "FastScale Startup",
        "notes": (
            "Emily needs a solution deployed by end of month or they'll lose a key client. "
            "$50k budget approved. Wants to skip the trial phase. "
            "Requested pricing for the annual plan today."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    assert_true(
        body["sentimentScore"] == "positive",
        f"Urgent+budget lead should be positive, got {body['sentimentScore']!r}",
    )
    return body


def tc06_minimal_notes():
    """Short but valid notes (just above 10-char minimum)."""
    status, body = post("/crm/analyze-lead", {
        "name": "Tom Baker",
        "company": "Baker & Associates",
        "notes": "Left voicemail. No response yet after two attempts this week.",
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    return body


def tc07_long_mixed_notes():
    """Long notes with mixed signals → positive or neutral sentiment."""
    status, body = post("/crm/analyze-lead", {
        "name": "Linda Park",
        "company": "MidWest Retail Co.",
        "notes": (
            "Initial call very promising — Linda was enthusiastic about our analytics. "
            "Follow-up calls revealed their board froze non-essential spending after a rough quarter. "
            "Linda personally wants to proceed and is lobbying the CFO. Asked for a detailed ROI breakdown. "
            "Timeline uncertain — Q4 this year or next fiscal. Still responsive to emails."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    assert_true(
        body["sentimentScore"] in {"positive", "neutral"},
        f"Mixed-signal lead should be positive or neutral, got {body['sentimentScore']!r}",
    )
    return body


def tc08_international_lead():
    """Non-ASCII company name and international context."""
    status, body = post("/crm/analyze-lead", {
        "name": "Yuki Tanaka",
        "company": "株式会社フューチャーテック (FutureTech KK)",
        "notes": (
            "Yuki reached out from Tokyo. They want to expand into European markets "
            "and need a CRM supporting multi-currency and multi-language. "
            "Very engaged, asked for a sandbox environment. Decision expected in 45 days."
        ),
    })
    assert_true(status == 200, f"Expected 200, got {status}")
    assert_analysis_shape(body)
    return body


def tc09_missing_name():
    """Missing 'name' field → 400 with error mentioning 'name'."""
    status, body = post("/crm/analyze-lead", {
        "company": "Acme Corp",
        "notes": "Interested in the enterprise plan. Demo booked for next week.",
    })
    assert_true(status == 400, f"Expected 400, got {status}")
    assert_true("error" in body, "Response must have 'error' field")
    assert_true(isinstance(body.get("details"), list), "'details' must be a list")
    assert_true(
        any("name" in d for d in body["details"]),
        "Error details must mention 'name'",
    )
    return body


def tc10_missing_company():
    """Missing 'company' field → 400 with error mentioning 'company'."""
    status, body = post("/crm/analyze-lead", {
        "name": "Jane Doe",
        "notes": "Very interested in our product. Wants a demo next week.",
    })
    assert_true(status == 400, f"Expected 400, got {status}")
    assert_true(
        any("company" in d for d in body.get("details", [])),
        "Error details must mention 'company'",
    )
    return body


def tc11_notes_too_short():
    """Notes under 10 chars → 400 with error mentioning 'notes'."""
    status, body = post("/crm/analyze-lead", {
        "name": "Mark Lee",
        "company": "Startup Inc",
        "notes": "OK",
    })
    assert_true(status == 400, f"Expected 400, got {status}")
    assert_true(
        any("notes" in d for d in body.get("details", [])),
        "Error details must mention 'notes'",
    )
    return body


def tc12_empty_body():
    """Empty body → 400 with all 3 field errors."""
    status, body = post("/crm/analyze-lead", {})
    assert_true(status == 400, f"Expected 400, got {status}")
    assert_true(
        len(body.get("details", [])) == 3,
        f"Expected 3 validation errors, got {len(body.get('details', []))}",
    )
    return body


# ── Test registry ─────────────────────────────────────────────────────────────

TESTS = [
    ("TC01", "Positive lead — strong interest & demo scheduled",   tc01_positive_lead),
    ("TC02", "Negative lead — uninterested, no budget",            tc02_negative_lead),
    ("TC03", "Neutral lead — exploratory multi-vendor evaluation", tc03_neutral_lead),
    ("TC04", "Enterprise lead — multi-team compliance process",    tc04_enterprise_lead),
    ("TC05", "Urgent lead — deadline + approved budget",           tc05_urgent_lead),
    ("TC06", "Minimal valid notes (just above 10-char minimum)",   tc06_minimal_notes),
    ("TC07", "Long notes with mixed signals",                      tc07_long_mixed_notes),
    ("TC08", "International lead — non-ASCII company name",        tc08_international_lead),
    ("TC09", "Missing 'name' field → 400",                        tc09_missing_name),
    ("TC10", "Missing 'company' field → 400",                     tc10_missing_company),
    ("TC11", "Notes too short (< 10 chars) → 400",                tc11_notes_too_short),
    ("TC12", "Empty body — all fields missing → 400",             tc12_empty_body),
]


# ── Runner ─────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{BOLD}{CYAN}{'━'*60}{RESET}")
    print(f"{BOLD}{CYAN}  AI CRM Assistant — Python/Gemini Test Suite ({len(TESTS)} tests){RESET}")
    print(f"{BOLD}{CYAN}  Target: {BASE_URL}{RESET}")
    print(f"{CYAN}{'━'*60}{RESET}\n")

    # Server health check
    try:
        status, health = get("/health")
        assert status == 200
        print(f"{GREEN}  Server online ✓  Model: {health.get('model', 'unknown')}{RESET}\n")
    except Exception:
        print(f"{RED}  ✗ Cannot reach server at {BASE_URL}{RESET}")
        print(f"  Run {BOLD}python src/server.py{RESET} in another terminal first.\n")
        sys.exit(1)

    passed, failed, failures = 0, 0, []
    results = []
    for tc_id, description, fn in TESTS:
        print(f"  {BOLD}{tc_id} — {description}{RESET}")
        try:
            result = fn()
            # Print key fields for functional tests
            if isinstance(result, dict) and "summary" in result:
                print(f"     {YELLOW}summary      :{RESET} {result['summary'][:90]}…" if len(result['summary']) > 90 else f"     {YELLOW}summary      :{RESET} {result['summary']}")
                print(f"     {YELLOW}followUp     :{RESET} {result['suggestedFollowUp'][:90]}…" if len(result['suggestedFollowUp']) > 90 else f"     {YELLOW}followUp     :{RESET} {result['suggestedFollowUp']}")
                print(f"     {YELLOW}sentiment    :{RESET} {result['sentimentScore']}")
            elif isinstance(result, dict) and "details" in result:
                print(f"     {YELLOW}errors       :{RESET} {'; '.join(result['details'])}")
            print(f"  {GREEN}✓ PASS{RESET}\n")
            passed += 1
            results.append({
                "test_id": tc_id,
                "description": description,
                "status": "PASS",
                "response": result,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
        except (AssertionError, Exception) as e:
            print(f"  {RED}✗ FAIL — {e}{RESET}\n")
            failed += 1
            failures.append((tc_id, description, str(e)))
            results.append({
                "test_id": tc_id,
                "description": description,
                "status": "FAIL",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
    print(f"{CYAN}{'━'*60}{RESET}")
    fail_color = RED if failed else ""
    print(
        f"{BOLD}  Results: {GREEN}{passed} passed{RESET}{BOLD}, "
        f"{fail_color}{failed} failed{RESET}{BOLD} / {len(TESTS)} total{RESET}"
    )

    if failures:
        print(f"\n{RED}  Failed tests:{RESET}")
        for tc_id, desc, err in failures:
            print(f"    • {tc_id} {desc}")
            print(f"      {err}")

    print(f"{CYAN}{'━'*60}{RESET}\n")
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f,indent=4,ensure_ascii=False)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
