"""
Komaru Anti-Slop Guardian — Streamlit App (English landing)
============================================================

Free tier (web demo): runs Anti-Slop engine on pasted text.
Pro tier (waitlist): email capture for launch notification (no public payment
in beta).

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
from en_copy import (
    BRAND_TITLE, BRAND_SUBTITLE, BRAND_FRAME_EN,
    PAGE_TITLE, PASTE_LABEL, PASTE_PLACEHOLDER, RUN_BUTTON,
    RESULT_NO_FLAGS, RESULT_NO_FLAGS_NUDGE,
    PRIVACY_NOTE, LIMITATION_NOTE,
    PRICING_HEADER, PRICING_TIERS, PRICING_NOTE,
    WAITLIST_HEADER, WAITLIST_INTRO,
    WAITLIST_EMAIL_LABEL, WAITLIST_EMAIL_PLACEHOLDER,
    WAITLIST_BUTTON, WAITLIST_PRIVACY,
    WAITLIST_INVALID, WAITLIST_EMPTY, WAITLIST_SUCCESS, WAITLIST_DUPLICATE,
)
from lead_capture import capture_lead, is_valid_email

# ============================================
# Page config — Heritage Navy + Gold theme
# ============================================
st.set_page_config(
    page_title=BRAND_TITLE,
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
# postMessage helpers
# ============================================
def emit_demo_paste(char_count: int):
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
    f"""
    <div style="text-align:center; padding: 0.5rem 0 1.5rem 0;">
      <h1 style="margin:0; color:#0F2A47; font-family: 'Montserrat', sans-serif; font-weight:700;">
        {BRAND_TITLE}
      </h1>
      <p style="margin:0.5rem 0 0; color:#5A6478; font-family:'Poppins', sans-serif;">
        {BRAND_SUBTITLE}
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(BRAND_FRAME_EN)

# ============================================
# UI — Input area
# ============================================
text = st.text_area(
    label=PASTE_LABEL,
    height=300,
    max_chars=UI_LIMITS["max_chars_hard_limit"],
    placeholder=PASTE_PLACEHOLDER,
    key="draft_text",
    label_visibility="visible",
)

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
        RUN_BUTTON,
        type="primary",
        use_container_width=True,
        disabled=not text or len(text.strip()) < UI_LIMITS["min_chars_for_filter"],
    )

if not text or len(text.strip()) < UI_LIMITS["min_chars_for_filter"]:
    st.caption(f"Minimum {UI_LIMITS['min_chars_for_filter']} characters required.")

# ============================================
# Filter execution
# ============================================
if run_clicked and text:
    with st.spinner("Scanning for AI-slop patterns..."):
        engine = AntiSlopEngine(tier=st.session_state["tier"])
        result = engine.analyze(text)
        st.session_state["result"] = result

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

    st.markdown("---")
    bar_cols = st.columns(4)
    bar_cols[0].metric("Flags", summary["total"])
    bar_cols[1].metric("Critical", summary["by_severity"].get("critical", 0))
    bar_cols[2].metric("High", summary["by_severity"].get("high", 0))
    bar_cols[3].metric("Words", stats["word_count"])

    st.markdown("### Findings")
    for i, f in enumerate(result["flags"], 1):
        sev_color = {
            "critical": "#B85C38",
            "high": "#D4A24C",
            "medium": "#5A6478",
            "low": "#95B098",
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
            f"""
            <div style="
                text-align: center;
                padding: 2rem;
                background: rgba(107, 142, 111, 0.08);
                border: 1px solid #6B8E6F;
                border-radius: 8px;
                font-family: 'Poppins', sans-serif;
            ">
              <div style="font-size: 2rem; color: #6B8E6F;">✓</div>
              <h3 style="color: #4F6E54; margin: 0.5rem 0;">{RESULT_NO_FLAGS.format(tier=st.session_state["tier"])}</h3>
              <p style="color: #5A6478; margin: 0;">{RESULT_NO_FLAGS_NUDGE}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================
# Pricing block
# ============================================
st.markdown("---")
st.subheader(PRICING_HEADER)
pcols = st.columns(len(PRICING_TIERS))
for i, t in enumerate(PRICING_TIERS):
    with pcols[i]:
        st.markdown(
            f"""
            <div style='border:1px solid #e5e7eb;padding:1rem;
                        border-radius:8px;height:200px;'>
              <div style='font-weight:700;color:#0F2A47;font-size:1.1rem;'>
                {t['name']}
              </div>
              <div style='color:#dc2626;font-weight:700;font-size:1.3rem;
                          margin:0.3rem 0;'>
                {t['price']}
              </div>
              <div style='color:#64748b;font-size:0.85rem;'>
                {t['alt']}
              </div>
              <div style='color:#374151;font-size:0.85rem;margin-top:0.5rem;'>
                {t['limits']}
              </div>
              <div style='color:#6b7280;font-size:0.78rem;font-style:italic;
                          margin-top:0.3rem;'>
                {t['ideal']}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
st.caption(PRICING_NOTE)

# ============================================
# Pro waitlist
# ============================================
st.markdown("---")
st.subheader(WAITLIST_HEADER)
st.markdown(WAITLIST_INTRO)

with st.form("pro_waitlist_form_en", clear_on_submit=False):
    waitlist_email = st.text_input(
        WAITLIST_EMAIL_LABEL,
        placeholder=WAITLIST_EMAIL_PLACEHOLDER,
        key="pro_waitlist_email_en",
    )
    submitted = st.form_submit_button(WAITLIST_BUTTON, type="primary")
    if submitted:
        if not waitlist_email.strip():
            st.warning(WAITLIST_EMPTY)
        elif not is_valid_email(waitlist_email):
            st.error(WAITLIST_INVALID)
        else:
            cap = capture_lead(
                email=waitlist_email,
                tier="Pro Monthly",
                source_page="Anti-Slop Guardian (EN)",
                notify_telegram=True,
            )
            if cap.ok and not cap.duplicate:
                st.success(WAITLIST_SUCCESS)
            elif cap.ok and cap.duplicate:
                st.info(WAITLIST_DUPLICATE)
            else:
                st.error(cap.message)

st.caption(WAITLIST_PRIVACY)

# ============================================
# Footer
# ============================================
st.markdown("---")
st.markdown(LIMITATION_NOTE)
st.markdown(PRIVACY_NOTE)

# Compact pricing recap + VN sibling cross-link
st.markdown(
    """
    <div style='color:#64748b;font-size:0.82rem;margin-top:1.2rem;
                padding-top:0.8rem;border-top:1px solid #e5e7eb;'>
      <b>Pricing:</b> Free (3 scans/day) · Pro Monthly $19/mo
      (₫350,000) — unlimited + full pattern library + API. ·
      <b>Also available:</b> <a href='/Soi_Van_Ban'
      style='color:#0F2A47;text-decoration:underline;'>Tiếng Việt →</a>
    </div>
    """,
    unsafe_allow_html=True,
)
