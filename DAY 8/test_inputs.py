"""
test_inputs.py – Test dataset
===============================
22 realistic support tickets covering all four categories.
Import TEST_INPUTS anywhere you need the test set.
"""

TEST_INPUTS = [
    # Bugs (broken / erroring)
    "My login keeps failing after the latest update to AuthPro. Error 403 every time I try. Username: john_doe.",
    "Sarah here from Acme Corp. Your API keeps returning 500 errors on /invoices endpoint since yesterday morning.",
    "The mobile app for FlowBoard crashes every time I open a project with more than 50 tasks. iOS 17.",
    "User: mike@corp.com. Product: BillingPlus. Issue: charged twice for the same invoice #INV-4421.",
    "Password reset email from SecureLogin never arrives. Checked spam. Tried 5 times today already.",
    "Files uploaded to DocuVault are corrupted when downloaded. Happens with files over 10MB.",
    "Search in KnowledgeBase is broken — it returns no results even for exact phrase matches.",
    "PayGate integration keeps rejecting valid Visa cards. Stripe test mode works fine. Live mode broken.",
    "NotifySend is sending duplicate push notifications. Every action triggers the alert 2-3 times.",

    # Feature requests
    "Would love a dark mode option in the DataDash dashboard. Our team works late and the bright white is tiring.",
    "Feature request: please add bulk CSV import to InventoryPro. Currently have to add items one by one.",
    "Requesting webhook support for StatusMonitor. We need real-time push instead of polling every 5 min.",
    "Please add two-factor authentication to AdminPortal. Our security team requires it for compliance.",
    "Would be great if SchedulerPro supported recurring events with custom RRULE expressions like iCal.",
    "Can SearchPro index content inside PDF attachments? We need full-text search across all file types.",

    # Questions
    "How do I export my reports as PDF in ReportBuilder? I can't find the option anywhere.",
    "Can you clarify the difference between the Pro and Enterprise plans for TeamSync? Pricing page is confusing.",
    "Is there an API rate limit for AnalyticsPro? We're hitting what looks like a 429 at ~200 req/min.",
    "How do I transfer my account from one workspace to another in CollabSpace?",
    "Need help setting up SSO with Okta for our OrgManager account. Following the docs but stuck at step 4.",

    # Complaints
    "This is absolutely unacceptable! My data in CloudStore was deleted without any warning. I want answers NOW.",
    "Extremely disappointed. SupportDesk has been down for 3 hours and your status page still says 'operational'.",
]