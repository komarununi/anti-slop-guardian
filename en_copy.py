"""
EN Copy — UI strings for Komaru Anti-Slop Guardian (English)
==============================================================

Mirror of vn_copy.py for the English landing page (main.py).

Voice principles (must match what the engine flags):
  - NO em-dash (the engine flags it as a key AI signal)
  - NO "X, Y, and Z" parallel triples (also flagged)
  - NO hyperbolic openers ("I'm excited to share", "Today I want to dive into")
  - NO banned-phrase verbs ("delve", "leverage", "multifaceted")
  - NO meta-narration ("In this section we will explore")
  - Reference voice: Notion docs, Stripe docs, Linear, Substack
  - Complete sentences, no fragments-as-sentences
  - Direct, action-oriented, professional but not stiff

Reframe-A locked: practical writing self-check, NO legal claim, NO forensic.
Pseudonym TIER 0: no real name / institution / credentials.
"""

# ---- Brand frame ----
BRAND_TITLE = "Komaru Anti-Slop Guardian"
BRAND_SUBTITLE = "Catch AI-slop patterns before you publish."
BRAND_FRAME_EN = (
    "A writing tool that flags phrases and patterns common in AI-generated "
    "prose. Use it to self-check your drafts before they go live."
)

# ---- Page ----
PAGE_TITLE = "Anti-Slop Guardian"
PASTE_LABEL = "Your draft"
PASTE_PLACEHOLDER = (
    "Blog post, marketing copy, email draft, product description. "
    "The engine works on any English prose. Minimum 50 characters."
)

RUN_BUTTON = "Check draft"

# ---- Result messages ----
RESULT_NO_FLAGS = "No AI-slop patterns detected on the {tier} tier."
RESULT_NO_FLAGS_NUDGE = (
    "Pro tier adds structural and density analysis on top of phrase patterns."
)

# ---- Footer ----
PRIVACY_NOTE = (
    "🔒 **Privacy.** Your text stays in this session. Closing the tab "
    "clears it. Each scan produces an SHA-256 hash so the same input "
    "yields the same result if you need to verify."
)

LIMITATION_NOTE = (
    "ℹ️ **Method limits.** False positives can occur with academic prose, "
    "translations, or text built from strict templates. Treat the result "
    "as a writing-quality signal, not an absolute verdict."
)

# ---- Pricing copy ----
PRICING_HEADER = "💰 Pricing"

PRICING_TIERS = [
    {
        "name": "Free",
        "price": "$0",
        "alt": "Free forever",
        "limits": "3 scans per day · Phrase patterns",
        "ideal": "Occasional self-checks",
    },
    {
        "name": "Pro Monthly",
        "price": "$19 / month",
        "alt": "₫350,000 / month",
        "limits": "Unlimited · Full pattern library · Structural analysis · API",
        "ideal": "Marketers, bloggers, editors who write daily",
    },
]

PRICING_NOTE = (
    "Beta May 2026: Pro launches at 30 percent off ($13 / month). "
    "Sign up below for the launch notification."
)

# ---- Pro waitlist (email-gated, no public payment) ----
WAITLIST_HEADER = "Get notified when Pro launches"
WAITLIST_INTRO = (
    "Pro is in beta. Drop your email below and we will send payment "
    "instructions when it goes live."
)
WAITLIST_EMAIL_LABEL = "Email"
WAITLIST_EMAIL_PLACEHOLDER = "you@example.com"
WAITLIST_BUTTON = "Notify me"
WAITLIST_PRIVACY = (
    "Email is used only for the Pro launch notification. Not shared with "
    "third parties. Request deletion at komarununi.business@gmail.com."
)
WAITLIST_INVALID = "That email looks invalid. Check the format."
WAITLIST_EMPTY = "Please enter an email."
WAITLIST_SUCCESS = (
    "Thanks. You will receive payment instructions by email when Pro "
    "launches in May 2026."
)
WAITLIST_DUPLICATE = (
    "This email is already on the waitlist. No need to register again."
)
