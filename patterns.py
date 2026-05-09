"""
Komaru Anti-Slop Guardian — Banned Phrases Database
====================================================

Source of truth: vault `brain/anti-ai-style.md` (sync 2026-05-10)

Pattern matching is CASE-INSENSITIVE by default unless `cs=True` flagged.
Each pattern includes:
- pattern: regex string
- rule: short rule ID for UI display
- replacement: suggested fix (or None)
- severity: critical | high | medium | low
- category: phrase | structure | density

CEO extends this list as new patterns surface from real writing audits.
"""

# ============================================
# BANNED PHRASES (zero tolerance)
# ============================================
# These trigger immediate flag with replacement suggestion.

BANNED_PHRASES = [
    {
        "pattern": r"\bdelve\s+into\b",
        "rule": "delve",
        "replacement": "examine, analyze, investigate",
        "severity": "critical",
        "category": "phrase",
        "why": "Top-3 AI tell. Generic, never specific."
    },
    {
        "pattern": r"\bshed(?:ding)?\s+light\s+on\b",
        "rule": "shed_light",
        "replacement": "show, reveal, illuminate (only if specific)",
        "severity": "critical",
        "category": "phrase",
        "why": "Cliché metaphor; AI reaches for it when stuck."
    },
    {
        "pattern": r"\bit\s+is\s+important\s+to\s+note\s+that\b",
        "rule": "important_to_note",
        "replacement": "(delete — nếu quan trọng, nói thẳng)",
        "severity": "critical",
        "category": "phrase",
        "why": "Filler. If important, the next clause should prove it."
    },
    {
        "pattern": r"\bit\s+should\s+be\s+noted\s+that\b",
        "rule": "should_be_noted",
        "replacement": "(delete)",
        "severity": "critical",
        "category": "phrase",
        "why": "Same as above. Cut filler."
    },
    {
        "pattern": r"\bit\s+is\s+worth\s+noting\b",
        "rule": "worth_noting",
        "replacement": "(delete)",
        "severity": "critical",
        "category": "phrase",
        "why": "Filler — readers can decide what's worth their attention."
    },
    {
        "pattern": r"\bin\s+today'?s\s+(?:rapidly\s+evolving\s+)?(?:landscape|world|society|era)\b",
        "rule": "today_landscape",
        "replacement": "(delete framing — get to point)",
        "severity": "critical",
        "category": "phrase",
        "why": "Generic AI opener; doesn't say anything."
    },
    {
        "pattern": r"\bnavigat(?:e|ing)\s+the\s+(?:landscape|complexities?|nuances?)\b",
        "rule": "navigate_landscape",
        "replacement": "be specific about what is being navigated",
        "severity": "critical",
        "category": "phrase",
        "why": "Empty metaphor. AI loves 'navigate'."
    },
    {
        "pattern": r"\bmultifaceted(?:\s+nature)?\b",
        "rule": "multifaceted",
        "replacement": "(describe specifically instead of generic adjective)",
        "severity": "high",
        "category": "phrase",
        "why": "Says 'has many sides' — every topic does. Useless."
    },
    {
        "pattern": r"\bby\s+leveraging\b|\bleverag(?:e|es|ed|ing)\b",
        "rule": "leverage",
        "replacement": "use, employ, draw on",
        "severity": "high",
        "category": "phrase",
        "why": "Business-jargon filler. 'Use' is fine."
    },
    {
        "pattern": r"\b(?:synergy|synergistic|synergiz(?:e|ing))\b",
        "rule": "synergy",
        "replacement": "(specify the combination explicitly)",
        "severity": "high",
        "category": "phrase",
        "why": "Corporate jargon. AI uses when it doesn't know specifics."
    },
    {
        "pattern": r"\bparadigm\s+shift\b",
        "rule": "paradigm_shift",
        "replacement": "(specify what changed)",
        "severity": "high",
        "category": "phrase",
        "why": "Cliché unless invoking Kuhn explicitly."
    },
    {
        "pattern": r"\bunlock(?:s|ing)?\s+(?:the\s+)?(?:potential|power|secret|possibilities)\b",
        "rule": "unlock_potential",
        "replacement": "(specify what is enabled and how)",
        "severity": "high",
        "category": "phrase",
        "why": "Marketing-AI overlap. Specifics > metaphor."
    },
    {
        "pattern": r"\bgroundbreaking\b",
        "rule": "groundbreaking",
        "replacement": "(specify what is new and why it matters)",
        "severity": "high",
        "category": "phrase",
        "why": "Hyperbole signal. Show, don't tell."
    },
    {
        "pattern": r"\brevolutionary\b",
        "rule": "revolutionary",
        "replacement": "(describe the actual change)",
        "severity": "high",
        "category": "phrase",
        "why": "Marketing hyperbole."
    },
    {
        "pattern": r"\bcutting[-\s]edge\b",
        "rule": "cutting_edge",
        "replacement": "(specify the technology and version)",
        "severity": "high",
        "category": "phrase",
        "why": "Trade-magazine cliché."
    },
    {
        "pattern": r"\bcomprehensive\s+(?:study|analysis|review|guide|overview)\b",
        "rule": "comprehensive",
        "replacement": "(let the scope speak — describe boundaries instead)",
        "severity": "medium",
        "category": "phrase",
        "why": "AI uses 'comprehensive' to claim authority without proof."
    },
    {
        "pattern": r"\brobust\s+(?:findings|results|methodology|framework)\b",
        "rule": "robust",
        "replacement": "consistent, reliable, strong (with evidence)",
        "severity": "medium",
        "category": "phrase",
        "why": "Overused. Earn the claim with numbers."
    },
    {
        "pattern": r"\bthe\s+findings\s+of\s+this\s+study\s+reveal\b",
        "rule": "findings_reveal",
        "replacement": "the data show, the analysis indicates",
        "severity": "medium",
        "category": "phrase",
        "why": "Academic AI tell. Passive + grandiose."
    },
    {
        "pattern": r"\bin\s+conclusion,?\s+this\s+(?:paper|study|article)\s+(?:has\s+)?(?:shown|demonstrated|established)\b",
        "rule": "in_conclusion_demonstrated",
        "replacement": "(restate the specific finding directly)",
        "severity": "medium",
        "category": "phrase",
        "why": "Formulaic conclusion opener."
    },
    {
        "pattern": r"\bthis\s+paper\s+proceeds\s+as\s+follows\b",
        "rule": "proceeds_as_follows",
        "replacement": "the analysis unfolds in X stages",
        "severity": "low",
        "category": "phrase",
        "why": "Boilerplate roadmap. Acceptable in formal academic but lazy."
    },
    # Marketing-specific (Tool A audience: writers, builders)
    {
        "pattern": r"\btapestry\b",
        "rule": "tapestry",
        "replacement": "(specific image instead)",
        "severity": "critical",
        "category": "phrase",
        "why": "Top AI metaphor cliché. 'Rich tapestry' = always AI."
    },
    {
        "pattern": r"\bintricate(?:ly)?\b",
        "rule": "intricate",
        "replacement": "(describe the actual complexity)",
        "severity": "high",
        "category": "phrase",
        "why": "Vague intensifier. Show the intricacy."
    },
    {
        "pattern": r"\bunderscore(?:s|d|ing)?\s+(?:the\s+)?(?:importance|need|significance)\b",
        "rule": "underscore_importance",
        "replacement": "(make the case directly)",
        "severity": "high",
        "category": "phrase",
        "why": "Telling, not showing."
    },
]

# ============================================
# STRUCTURAL PATTERNS (heuristics, count-based)
# ============================================

STRUCTURAL_RULES = [
    {
        "rule": "em_dash_density",
        "check": "em_dash_per_1000_chars",
        "threshold_high": 3.0,   # >3 per 1000 chars = AI-tell
        "threshold_critical": 5.0,
        "severity_high": "medium",
        "severity_critical": "high",
        "why": "AI overuses em-dash for rhythm. 1-2 per page natural.",
        "fix": "Replace some with periods or commas. Keep <3 per 1000 chars body voice."
    },
    {
        "rule": "the_paragraph_opener",
        "check": "paragraphs_starting_with_the",
        "threshold_high": 0.5,   # >50% paragraphs start with "The"
        "threshold_critical": 0.7,
        "severity_high": "medium",
        "severity_critical": "high",
        "why": "AI defaults to 'The X is...' as paragraph opener.",
        "fix": "Vary openers. Use names, fragments, questions, transitions."
    },
    {
        "rule": "consecutive_the_sentences",
        "check": "max_consecutive_the_sentence_starts",
        "threshold_high": 3,     # 3+ sentences in a row starting "The"
        "threshold_critical": 4,
        "severity_high": "high",
        "severity_critical": "critical",
        "why": "Sequential 'The...' starters = AI rhythm flat.",
        "fix": "Vary 2nd or 3rd sentence with subject swap or fragment."
    },
    {
        "rule": "parallel_triples",
        "check": "x_y_and_z_pattern_per_1000_words",
        "threshold_high": 4.0,   # >4 parallel triples per 1000 words
        "threshold_critical": 8.0,
        "severity_high": "medium",
        "severity_critical": "high",
        "why": "AI loves 'X, Y, and Z' lists. Real writing varies 2/3/4.",
        "fix": "Mix list lengths. Some 2-item, some 4-item, some prose-blended."
    },
    {
        "rule": "uniform_sentence_length",
        "check": "sentence_length_variance",
        "threshold_low": 4.0,    # variance < 4 = too uniform
        "severity_low": "low",
        "why": "Real prose has mix of short + long. AI defaults to medium.",
        "fix": "Add 1-2 short sentences (<10 words) per paragraph for rhythm."
    },
]


# ============================================
# MIN/MAX text constraints (UI guard)
# ============================================

UI_LIMITS = {
    "min_chars_for_filter": 50,        # Below = too short to analyze
    "max_chars_recommended": 5000,     # Above = warn user, may slow
    "max_chars_hard_limit": 50000,     # DOS guard
    "debounce_ms": 500,                # postMessage debounce
}


# ============================================
# Tier-gated patterns (Pro / Bundle features)
# ============================================
# Free tier: only `category in {"phrase"} and severity in {"critical"}`.
# Pro tier: all phrase + structural rules.
# Bundle: Pro + custom user-defined patterns + API access.

TIER_ACCESS = {
    "free": {
        "categories": ["phrase"],
        "severities": ["critical"],
        "description": "Catches the most egregious AI tells (delve, tapestry, underscore, etc)",
    },
    "pro": {
        "categories": ["phrase", "structure", "density"],
        "severities": ["critical", "high", "medium", "low"],
        "description": "Full pattern library + structural analysis + density checks",
    },
    "bundle": {
        "categories": ["phrase", "structure", "density", "custom"],
        "severities": ["critical", "high", "medium", "low"],
        "description": "Pro + 30 voice-preserving prompts + custom rules + API",
    },
}
