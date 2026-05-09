# Komaru Anti-Slop Guardian — Streamlit App

> Tool A engine: pure-regex AI-slop pattern detection for writers.
> Free tier (web demo) + Pro tier ($9/mo) + Bundle ($39 one-time).

---

## Architecture

```
src/streamlit-app/
├── main.py             # UI + postMessage hooks (per Q3 contract v1.0)
├── anti_slop_engine.py # Pure-regex pattern matching engine
├── patterns.py         # Banned phrases + structural rules data
├── requirements.txt    # streamlit only (zero LLM, zero API)
├── .streamlit/
│   └── config.toml    # Heritage Navy + Gold theme
└── README.md          # This file
```

**Design principle:** No LLM, no API call, no opaque "AI detection". Pure regex + counting + thresholds. Users can audit every flag via `patterns.py`.

---

## Quick start (local dev)

```powershell
cd E:\PhD_HNUE\Claude_Code\komaru-marketing\src\streamlit-app

# Setup venv (recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install + run
pip install -r requirements.txt
streamlit run main.py

# Open http://localhost:8501
```

Smoke test:
```powershell
python anti_slop_engine.py   # Run module-level test on hard-coded sample
```

---

## Deploy to Streamlit Community Cloud

1. Push `src/streamlit-app/` contents to a GitHub repo (e.g. `komaru/anti-slop-guardian`)
2. Go to https://share.streamlit.io → New app
3. Connect repo, set:
   - Main file: `main.py`
   - Branch: `main`
4. After deploy, set custom subdomain: `anti-slop.streamlit.app`
5. Verify origin: wrapper page (Tailwind) hardcodes `'https://anti-slop.streamlit.app'` — must match.

---

## postMessage Events (per Q3 contract v1.0)

Streamlit emits 2 events to parent window via `window.parent.postMessage(...)`:

| Event | When | Payload |
|-------|------|---------|
| `demo_paste` | User changes text (debounced 500ms via `session_state` hash guard) | `{type: 'demo_paste', char_count: N}` |
| `demo_run`   | After filter completes successfully (guarded against double-fire) | `{type: 'demo_run', flag_count: N}` |

**Wrapper listener** (Tailwind page) consumes these and forwards to Plausible Analytics. See `plans/.../phase-04-deploy-package-lemonsqueezy-webhook-plausible-env-template.md` for parent-side implementation.

---

## Tier gating (`patterns.py` `TIER_ACCESS`)

| Tier | Categories | Severities | Notes |
|------|-----------|-----------|-------|
| **Free** | phrase | critical only | Catches top AI tells (delve, tapestry, underscore...) |
| **Pro** | phrase + structure + density | critical + high + medium + low | Full pattern library + structural analysis |
| **Bundle** | + custom | all | Pro + 30 voice prompts + custom rules + API |

Free tier is hardcoded to `tier="free"` in `main.py`. Pro/Bundle tier-switching deferred to W2 deploy with auth integration.

---

## Extending patterns

CEO adds new banned phrases to `patterns.py` `BANNED_PHRASES` list. Each entry:

```python
{
    "pattern": r"\bregex_here\b",          # Word boundary recommended
    "rule": "short_id",                     # Used in UI display
    "replacement": "what to use instead",   # Suggestion string
    "severity": "critical|high|medium|low",
    "category": "phrase|structure|density",
    "why": "1-line explanation for user",
}
```

Test new patterns:
```powershell
python anti_slop_engine.py
```

---

## Sync source of truth

`patterns.py` mirrors vault `brain/anti-ai-style.md`. When vault updates:

1. CEO updates vault `brain/anti-ai-style.md`
2. Re-sync `patterns.py` (manual port for now; auto-sync deferred)
3. Increment version in `main.py` header (track schema drift)

---

## Mandatory dogfood (brand-integrity loop)

**Before announcing on LinkedIn:** paste rendered landing page HTML through Tool A's own free tier. If filter flags anything in native voice (anything outside `<code>` tags), iterate.

→ Tool eats own dogfood. Hypocrisy gate held.

---

## Ship checklist (Sun 11/5/2026)

- [ ] Local smoke test (`streamlit run main.py`) — text paste, filter run, results render
- [ ] Verify postMessage events fire (browser DevTools console)
- [ ] Push to GitHub `komaru/anti-slop-guardian`
- [ ] Deploy on streamlit.io/cloud, set domain `anti-slop.streamlit.app`
- [ ] Test iframe inside Tailwind wrapper (origin filter passes)
- [ ] Verify Plausible events arrive in dashboard
- [ ] Final dogfood (paste landing page through filter)
- [ ] LinkedIn Day 4 post + Substack first essay live
