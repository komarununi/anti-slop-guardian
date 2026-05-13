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
    # Bundle leads per Council 2026-05-14 #1 (Sahil "lead-with-bundle")
    {
        "name": "Lifetime",
        "price": "$39 one-time",
        "alt": "₫990,000 lifetime",
        "limits": "Unlimited · Full library · 12-month warranty · 7-day refund",
        "ideal": "Writers who hate subscriptions — pay once, use forever",
    },
    {
        "name": "Pro Monthly",
        "price": "$19 / month",
        "alt": "₫350,000 / month",
        "limits": "Unlimited · Full pattern library · Cancel anytime",
        "ideal": "Agencies who want to try-before-commit",
    },
]

PRICING_NOTE = (
    "W2 launch (May 20-26): manual checkout via Telegram, 6h reply SLA. "
    "Sepay automated W3, Stripe international W4."
)

# ---- Buy-Now section (W2 manual launch, added 2026-05-14) ----
# Per Business Council 2026-05-14 #2: Telegram-manual W2 → Sepay W3 → Stripe W4
BUY_NOW_HEADER = "🚀 Buy now (Lifetime bundle)"
BUY_NOW_INTRO = (
    "This week (W2 launch, May 20-26), Komaru handles orders manually via "
    "Telegram within 6h. After Stripe goes live (week 4), you can pay "
    "instantly by card."
)
BUY_NOW_BUNDLE_NAME = "Anti-Slop Guardian — Lifetime Bundle"
BUY_NOW_BUNDLE_PRICE_VND = "₫990,000"
BUY_NOW_BUNDLE_PRICE_USD = "$39 (one-time)"
BUY_NOW_BUNDLE_DESC = (
    "One-time payment · Lifetime access · Full pattern library · Export · "
    "12-month warranty · 7-day refund window"
)
BUY_NOW_BUTTON_LABEL = "💬 Contact Komaru on Telegram"
BUY_NOW_PREFILL = (
    "Hi Komaru, I would like to buy the Anti-Slop Lifetime Bundle ($39). "
    "Please send payment instructions."
)
BUY_NOW_FALLBACK = (
    "No Telegram? Email komarununi.business@gmail.com with the same message."
)
BUY_NOW_FOOTNOTE = (
    "W2 manual: reply within 6h (Vietnam time, GMT+7). Wise/PayPal for "
    "international · VietQR for VN buyers. License key delivered after "
    "payment confirmation."
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
