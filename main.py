"""
Komaru Anti-Slop Guardian — Streamlit App
==========================================

Free tier (web demo): runs Anti-Slop engine on pasted text.
Pro tier ($9/mo): full pattern library + custom rules (deferred to W2 deploy).

postMessage contract: per `plans/.../streamlit-postmessage-contract-spec-...md` v1.0
- demo_paste: fired on text change (debounced 500ms server-side via session_state)
- demo_run:   fired after filter completes successfully

Run locally:
    cd src/streamlit-app
    pip install -r requirements.txt
    streamlit run main.py

Deploy:
    streamlit.io/cloud → connect GitHub → set custom domain anti-slop.streamlit.app
"""

import hashlib
import streamlit as st
import streamlit.components.v1 as components
from anti_slop_engine import AntiSlopEngine
from patterns import UI_LIMITS, TIER_ACCESS

# ============================================
# Page config — Heritage Navy + Gold theme
# ============================================
st.set_page_config(
    page_title="Komaru Anti-Slop Guardian",
    page_icon="📜",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============================================
# Session state init
# ============================================
def _init_state():
    defaults = {
        "tier": "free",
        "last_paste_hash": None,
        "demo_run_fired_for": None,
        "result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ============================================
# postMessage helpers (per Q3 contract spec v1.0)
# ============================================
def emit_demo_paste(char_count: int):
    """Fire demo_paste event to parent window (Tailwind wrapper)."""
    components.html(
        f"""
        <script>
        (function() {{
          clearTimeout(window.__komaruPasteTimer);
          window.__komaruPasteTimer = setTimeout(function() {{
            window.parent.postMessage({{
              type: 'demo_paste',
              char_count: {char_count}
            }}, '*');
          }}, {UI_LIMITS["debounce_ms"]});
        }})();
        </script>
        """,
        height=0,
    )

def emit_demo_run(flag_count: int):
    """Fire demo_run event to parent window after filter completes."""
    components.html(
        f"""
        <script>
        window.parent.postMessage({{
          type: 'demo_run',
          flag_count: {flag_count}
        }}, '*');
        </script>
        """,
        height=0,
    )

# ============================================
# UI — Header
# ============================================
st.markdown(
    """
    <div style="text-align:center; padding: 0.5rem 0 1.5rem 0;">
      <h1 style="margin:0; color:#0F2A47; font-family: 'Montserrat', sans-serif; font-weight:700;">
        Komaru Anti-Slop Guardian
      </h1>
      <p style="margin:0.5rem 0 0; color:#5A6478; font-family:'Poppins', sans-serif;">
        Your text doesn't sound like AI.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================
# UI — Input area
# ============================================
text = st.text_area(
    label="Paste your draft",
    height=300,
    max_chars=UI_LIMITS["max_chars_hard_limit"],
    placeholder="Paste your writing here. We flag AI-slop patterns — banned phrases, em-dash overuse, parallel triples, generic openers — so your voice stays human.",
    key="draft_text",
    label_visibility="collapsed",
)

# Fire demo_paste with double-fire guard (Q2 spec resolution)
if text:
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    if st.session_state["last_paste_hash"] != text_hash:
        st.session_state["last_paste_hash"] = text_hash
        emit_demo_paste(len(text))

# ============================================
# UI — Filter button
# ============================================
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    run_clicked = st.button(
        "Run my draft through the filter",
        type="primary",
        use_container_width=True,
        disabled=not text or len(text.strip()) < UI_LIMITS["min_chars_for_filter"],
    )

if not text or len(text.strip()) < UI_LIMITS["min_chars_for_filter"]:
    st.caption(f"_(Need at least {UI_LIMITS['min_chars_for_filter']} characters to analyze.)_")

# ============================================
# Filter execution
# ============================================
if run_clicked and text:
    with st.spinner("Scanning for AI-slop patterns…"):
        engine = AntiSlopEngine(tier=st.session_state["tier"])
        result = engine.analyze(text)
        st.session_state["result"] = result

    # Fire demo_run (with double-fire guard)
    if st.session_state["demo_run_fired_for"] != text_hash:
        st.session_state["demo_run_fired_for"] = text_hash
        emit_demo_run(result["summary"]["total"])

# ============================================
# UI — Results display
# ============================================
result = st.session_state.get("result")

if result and result["flags"]:
    summary = result["summary"]
    stats = result["stats"]

    # Summary bar
    st.markdown("---")
    bar_cols = st.columns(4)
    bar_cols[0].metric("Flags", summary["total"])
    bar_cols[1].metric("Critical", summary["by_severity"].get("critical", 0))
    bar_cols[2].metric("High", summary["by_severity"].get("high", 0))
    bar_cols[3].metric("Words", stats["word_count"])

    # Per-flag details
    st.markdown("### Findings")
    for i, f in enumerate(result["flags"], 1):
        sev_color = {
            "critical": "#B85C38",  # Terracotta
            "high": "#D4A24C",      # Gold
            "medium": "#5A6478",    # Text secondary
            "low": "#95B098",       # Sage light
        }.get(f["severity"], "#5A6478")

        with st.container():
            st.markdown(
                f"""
                <div style="
                    border-left: 3px solid {sev_color};
                    padding: 0.75rem 1rem;
                    margin: 0.5rem 0;
                    background: #F4EFE6;
                    border-radius: 4px;
                    font-family: 'Poppins', sans-serif;
                ">
                  <div style="color:{sev_color}; font-weight:600; font-size:0.85rem; text-transform:uppercase;">
                    {f['severity']} · {f['rule']}
                  </div>
                  <div style="color:#1A2333; margin:0.25rem 0; font-family: 'JetBrains Mono', monospace; font-size:0.9rem;">
                    {f['snippet']}
                  </div>
                  <div style="color:#5A6478; font-size:0.85rem;">
                    <strong>Suggestion:</strong> {f['suggestion']}
                  </div>
                  <div style="color:#5A6478; font-size:0.8rem; font-style:italic; margin-top:0.25rem;">
                    {f['why']}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

elif result and not result["flags"]:
    if result.get("skip_reason") == "too_short":
        st.info(f"Text too short. Need at least {UI_LIMITS['min_chars_for_filter']} characters.")
    elif result.get("skip_reason") == "too_long":
        st.warning(f"Text too long. Max {UI_LIMITS['max_chars_hard_limit']} characters.")
    else:
        st.markdown(
            """
            <div style="
                text-align: center;
                padding: 2rem;
                background: rgba(107, 142, 111, 0.08);
                border: 1px solid #6B8E6F;
                border-radius: 8px;
                font-family: 'Poppins', sans-serif;
            ">
              <div style="font-size: 2rem; color: #6B8E6F;">✓</div>
              <h3 style="color: #4F6E54; margin: 0.5rem 0;">No AI-slop patterns detected</h3>
              <p style="color: #5A6478; margin: 0;">
                On the {tier} tier, your draft passes. Pro tier adds structural + density checks.
              </p>
            </div>
            """.format(tier=st.session_state["tier"]),
            unsafe_allow_html=True,
        )

# ============================================
# UI — Footer (free tier nudge to Pro)
# ============================================
if st.session_state["tier"] == "free":
    filtered = result["filtered_count"] if result else len([])
    st.markdown("---")
    st.markdown(
        f"""
        <div style="
            text-align: center;
            color: #5A6478;
            font-family: 'Poppins', sans-serif;
            font-size: 0.9rem;
            padding: 1rem;
        ">
          Free tier catches the most egregious AI tells.
          <strong style="color: #0F2A47;">Pro ($9/mo)</strong> adds structural patterns,
          density checks, and {len(TIER_ACCESS["pro"]["categories"])} categories of analysis.
          <br/>
          <a href="#pricing" style="color:#D4A24C; text-decoration:none; font-weight:600;">
            See Pro features →
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
