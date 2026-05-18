"""
Komaru Anti-Slop · Tiếng Việt — Streamlit page
================================================

Multi-page tab in Tool A. Default landing = English Anti-Slop Guardian.
This page = VN sibling: practical writing self-check, NOT forensic/legal.

Reframe locked 2026-05-13 (Reframe-A):
  - Frame: "Bài viết của bạn có nghe như AI không?"
  - Use case: marketer, blogger, editor self-check
  - NO legal claim · NO Công văn 314 · NO disclaimer pháp lý

Run via parent app:
  streamlit run main.py
Sidebar auto-discovers "Soi Van Ban".
"""
import sys
from pathlib import Path

# Allow importing engine from parent dir
APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

import streamlit as st

from vn_origin_engine import analyze, AuthorshipReport
from vn_suggestions import build_suggestions, suggestions_to_dicts
from vn_export import build_export_payload
# AppSec wiring 2026-05-19: license gate + rate limit on Layer 3
from license_db import validate_license, LICENSE_KEY_PATTERN
from rate_limiter import check as rate_check
from vn_copy import (
    BRAND_TITLE, BRAND_SUBTITLE, BRAND_FRAME_VN,
    PAGE_TITLE, PAGE_HEADER, PAGE_INTRO,
    PASTE_LABEL, PASTE_PLACEHOLDER, RUN_BUTTON, RUN_BUTTON_LLM,
    VERDICT_LABELS, VERDICT_EXPLANATION, CONFIDENCE_LABELS,
    SEC_OVERALL, SEC_LAYERS, SEC_EVIDENCE, SEC_RUBRIC,
    SEC_SUGGESTIONS, SEC_SUGGESTIONS_EMPTY, SUGGESTIONS_INTRO,
    SUGGESTION_HIT_LABEL,
    LAYER_NAMES, PRIVACY_NOTE, LIMITATION_NOTE,
    PRICING_HEADER, PRICING_TIERS, PRICING_NOTE_VN, SAMPLES,
    WAITLIST_HEADER, WAITLIST_INTRO,
    WAITLIST_EMAIL_LABEL, WAITLIST_EMAIL_PLACEHOLDER,
    WAITLIST_BUTTON, WAITLIST_PRIVACY,
)
from lead_capture import capture_lead, is_valid_email
from buy_now_section import render_buy_now_section
import vn_copy

st.set_page_config(
    page_title=f"{BRAND_TITLE} — {PAGE_TITLE}",
    page_icon="📝",
    layout="centered",
)

# ---- Header ----
st.markdown(
    f"""
    <div style='text-align:center; padding:0.5rem 0 1.2rem 0;'>
      <h1 style='margin:0; color:#0F2A47;'>{PAGE_HEADER}</h1>
      <p style='margin:0.4rem 0 0; color:#5A6478;'>{BRAND_SUBTITLE}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(PAGE_INTRO)

# ---- Sample picker ----
with st.expander("📝 Sử dụng văn bản mẫu"):
    sample_choice = st.selectbox(
        "Chọn mẫu",
        ["(không sử dụng mẫu)"] + list(SAMPLES.keys()),
        index=0,
    )
    if sample_choice != "(không sử dụng mẫu)":
        if st.button("Sử dụng mẫu này", key="paste_sample"):
            st.session_state["draft_text"] = SAMPLES[sample_choice]

# ---- Input ----
text = st.text_area(
    label=PASTE_LABEL,
    height=280,
    max_chars=20000,
    placeholder=PASTE_PLACEHOLDER,
    key="draft_text",
    label_visibility="visible",
)

# ---- LLM toggle (default off until API key wired in deploy) ----
# AppSec gate 2026-05-19: Layer 3 (Claude LLM) requires:
#   1. ANTHROPIC_API_KEY env var (infra prereq)
#   2. Valid Komaru Pro/Bundle license (KMR-XXXXXXXX-XXXX-XXXXXXXX)
#   3. Per-session rate limit (50/hour, scope=llm_layer3_per_session)
import os
llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))

# Persist validated license across reruns (Streamlit re-executes the page on
# every interaction). Re-validate when key changes.
if "license_validated" not in st.session_state:
    st.session_state["license_validated"] = False
    st.session_state["license_plan"] = None
    st.session_state["license_key_input"] = ""

with st.expander("🔑 Mã kích hoạt Pro/Bundle (mở Lớp 3 Claude)", expanded=False):
    st.caption(
        "Mã có dạng `KMR-XXXXXXXX-XXXX-XXXXXXXX` (26 ký tự). "
        "Mua tại trang chính · 7-day refund · không chia sẻ mã."
    )
    license_input = st.text_input(
        "License key",
        value=st.session_state.get("license_key_input", ""),
        placeholder="KMR-XXXXXXXX-XXXX-XXXXXXXX",
        type="password",
        key="license_input_field",
        max_chars=32,
        label_visibility="collapsed",
    )
    col_l1, col_l2 = st.columns([1, 3])
    with col_l1:
        validate_clicked = st.button("Kích hoạt", use_container_width=True)
    with col_l2:
        if st.session_state["license_validated"]:
            st.success(
                f"✅ Đã kích hoạt — gói **{st.session_state['license_plan'].upper()}**"
            )

    if validate_clicked and license_input:
        # Get IP best-effort (Streamlit doesn't expose easily; fall back to session id)
        client_ip = st.context.headers.get("x-forwarded-for", "") if hasattr(st, "context") else ""
        if not client_ip:
            client_ip = f"sess-{st.session_state.get('_session_id', 'unknown')}"
        result = validate_license(license_input.strip(), ip=client_ip)
        if result.valid:
            st.session_state["license_validated"] = True
            st.session_state["license_plan"] = result.plan
            st.session_state["license_key_input"] = license_input.strip()
            st.rerun()
        else:
            if result.locked_out:
                st.error(
                    "⛔ Quá nhiều lần thử sai từ địa chỉ này. "
                    "Thử lại sau 24 giờ hoặc liên hệ support."
                )
            else:
                st.error(f"❌ {result.reason}")

# Layer 3 available only when API key configured AND license valid
layer3_unlocked = llm_available and st.session_state["license_validated"]

col_a, col_b = st.columns([3, 1])
with col_a:
    use_llm = st.toggle(
        "Bật Claude (Lớp 3, lâu hơn vài giây)",
        value=False,
        disabled=not layer3_unlocked,
        help=(
            "Bản Free sử dụng Lớp 1 và 2. Bản Pro/Bundle mở thêm Lớp 3 — "
            "nhập mã kích hoạt ở mục trên."
        ) if not layer3_unlocked else None,
    )
with col_b:
    run_clicked = st.button(
        RUN_BUTTON if not use_llm else RUN_BUTTON_LLM,
        type="primary",
        use_container_width=True,
        disabled=not text or len(text.strip()) < 100,
    )

if text and len(text.strip()) < 100:
    st.caption(f"⚠️ Cần tối thiểu 100 ký tự. Hiện có {len(text.strip())}.")

# ---- Run ----
if run_clicked and text:
    # Rate limit Layer 3 calls (paid users still capped to prevent cost bleed
    # OR shared-license abuse).
    if use_llm:
        session_key = st.session_state.get("license_key_input") or \
                      f"anon-{st.session_state.get('_session_id', 'unknown')}"
        rl = rate_check("llm_layer3_per_session", session_key)
        if not rl.allowed:
            st.error(
                f"⏱️ Đã vượt giới hạn Lớp 3 ({rl.limit} lượt / "
                f"{rl.window_seconds // 60} phút). "
                f"Thử lại sau {rl.retry_after_seconds // 60} phút."
            )
            st.stop()

    with st.spinner("Đang phân tích…"):
        try:
            report = analyze(text, use_llm=use_llm)
            st.session_state["vn_report"] = report
        except (ValueError, TypeError) as e:
            st.error(f"❌ {e}")
            st.session_state["vn_report"] = None

report: AuthorshipReport = st.session_state.get("vn_report")

# ---- Render report ----
if report:
    st.markdown("---")

    # Overall verdict
    st.subheader(SEC_OVERALL)
    label, color = VERDICT_LABELS.get(report.verdict, ("?", "#64748b"))
    st.markdown(
        f"""
        <div style='border-left:6px solid {color};
                    padding:1rem 1.2rem;background:#0f172a08;
                    border-radius:6px;margin:0.6rem 0;'>
          <div style='font-size:1.4rem;font-weight:700;color:{color};'>
            {label} · điểm tổng: {report.overall_score}/100
          </div>
          <div style='color:#475569;margin-top:0.4rem;'>
            {VERDICT_EXPLANATION.get(report.verdict, "")}
          </div>
          <div style='color:#64748b;font-size:0.85rem;margin-top:0.3rem;'>
            Độ tin cậy: <b>{CONFIDENCE_LABELS.get(report.confidence, report.confidence)}</b>
            · hash: <code>{report.text_hash[:16]}…</code>
            · {report.timestamp_iso}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Per-layer scores
    st.subheader(SEC_LAYERS)
    cols = st.columns(3)
    for i, k in enumerate(["regex", "statistical", "llm"]):
        weight = report.layer_weights.get(k, 0.0)
        score = report.layer_scores.get(k, 0)
        cols[i].metric(
            LAYER_NAMES[k],
            f"{score}/100",
            help=f"Trọng số: {weight*100:.0f}%",
        )

    # Statistical profile detail
    with st.expander("📊 Đặc trưng thống kê chi tiết"):
        p = report.statistical
        st.markdown(
            f"""
            - Số ký tự: **{p.char_count}**
            - Số từ: **{p.word_count}**
            - Số câu: **{p.sentence_count}** (trung bình {p.avg_sentence_words:.1f} từ/câu)
            - Số đoạn: **{p.para_count}** (σ độ dài {p.para_length_stdev:.0f} ký tự)
            - **Burstiness** (σ độ dài câu): {p.burstiness:.2f}
            - **TTR** (vốn từ / 100 từ): {p.ttr_per_100w:.2f}
            - **Liên từ trang trọng / 100 từ**: {p.formal_connector_per_100w:.1f}
            - **Em-dash / 1000 ký tự**: {p.dash_per_1000_chars:.1f}
            """
        )

    # LLM rubric (if available)
    if report.llm.available:
        st.subheader(SEC_RUBRIC)
        st.markdown(f"**Verdict Claude:** `{report.llm.verdict}` · "
                    f"AI likelihood: **{report.llm.overall_ai_likelihood}/100**")
        if report.llm.scores:
            score_cols = st.columns(len(report.llm.scores))
            for i, (k, v) in enumerate(report.llm.scores.items()):
                score_cols[i].metric(k, f"{v}/100")
        if report.llm.evidence:
            st.markdown("**Bằng chứng:**")
            for e in report.llm.evidence:
                st.markdown(f"- {e}")
        if report.llm.caveats:
            st.markdown("**Hạn chế:**")
            for c in report.llm.caveats:
                st.markdown(f"- _{c}_")
        st.caption(f"Đã ẩn {report.llm.redactions_applied} chi tiết riêng "
                   f"tư trước khi gửi Claude.")
    elif report.llm.error:
        st.caption("_Lớp 3 chưa được bật._")

    # Evidence list
    st.subheader(SEC_EVIDENCE)
    if not report.evidence:
        st.success("Không phát hiện dấu hiệu AI cụ thể.")
    else:
        sev_color = {
            "critical": "#dc2626", "high": "#ea580c",
            "medium": "#f59e0b", "low": "#facc15", "info": "#64748b",
        }
        for ev in report.evidence:
            color = sev_color.get(ev.severity, "#64748b")
            st.markdown(
                f"""
                <div style='border-left:3px solid {color};
                            padding:0.5rem 0.8rem;margin:0.3rem 0;
                            background:#fafafa;border-radius:3px;
                            font-size:0.92rem;'>
                  <div style='color:{color};font-weight:600;font-size:0.78rem;
                              text-transform:uppercase;'>
                    [{ev.layer}] {ev.severity} · {ev.rule}
                  </div>
                  <div style='color:#1f2937;font-family:monospace;
                              margin:0.2rem 0;font-size:0.85rem;'>
                    {ev.snippet}
                  </div>
                  <div style='color:#475569;font-size:0.82rem;'>
                    {ev.explanation}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---- Suggestions block ----
    st.subheader(SEC_SUGGESTIONS)
    suggestions = build_suggestions(report)
    if not suggestions:
        st.info(SEC_SUGGESTIONS_EMPTY)
    else:
        st.caption(SUGGESTIONS_INTRO)
        sev_color_sug = {
            "critical": "#dc2626", "high": "#ea580c",
            "medium": "#f59e0b", "low": "#facc15", "info": "#64748b",
        }
        for s in suggestions:
            color = sev_color_sug.get(s.severity, "#64748b")
            hit_badge = (
                f"<span style='color:#64748b;font-size:0.75rem;'>"
                f"{s.hit_count} {SUGGESTION_HIT_LABEL}</span>"
                if s.hit_count > 1 else ""
            )
            st.markdown(
                f"""
                <div style='border-left:4px solid {color};
                            padding:0.7rem 1rem;margin:0.5rem 0;
                            background:#fafafa;border-radius:4px;'>
                  <div style='display:flex;justify-content:space-between;
                              align-items:center;margin-bottom:0.4rem;'>
                    <div style='color:{color};font-weight:600;font-size:0.85rem;
                                text-transform:uppercase;'>
                      {s.severity} · {s.rule}
                    </div>
                    {hit_badge}
                  </div>
                  <div style='color:#1f2937;margin:0.3rem 0;font-size:0.92rem;'>
                    <b>Gợi ý:</b> {s.rewrite_hint}
                  </div>
                  <div style='color:#475569;font-size:0.82rem;
                              font-style:italic;'>
                    {s.why}
                  </div>
                  <div style='color:#94a3b8;font-size:0.78rem;
                              margin-top:0.4rem;font-family:monospace;'>
                    ví dụ: {s.example_snippet[:140]}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # JSON download — canonical schema 1.1 via vn_export
    import json
    payload = build_export_payload(report, suggestions)
    st.download_button(
        "⬇️ Tải kết quả (JSON)",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name=f"soi_van_ban_{report.text_hash[:12]}.json",
        mime="application/json",
        help=f"Schema {payload['schema_version']} · không chứa thông tin "
             f"nhận diện cá nhân",
    )

# ---- Pricing block ----
st.markdown("---")
st.subheader(PRICING_HEADER)
pcols = st.columns(len(PRICING_TIERS))
for i, t in enumerate(PRICING_TIERS):
    with pcols[i]:
        st.markdown(
            f"""
            <div style='border:1px solid #e5e7eb;padding:1rem;
                        border-radius:8px;min-height:200px;'>
              <div style='font-weight:700;color:#0F2A47;font-size:1.1rem;'>
                {t['name']}
              </div>
              <div style='color:#dc2626;font-weight:700;font-size:1.3rem;
                          margin:0.3rem 0;'>
                {t['vnd']}
              </div>
              <div style='color:#64748b;font-size:0.85rem;'>
                {t['usd']}
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
st.caption(PRICING_NOTE_VN)

# ---- Buy-Now (W2 manual launch, added 2026-05-14) ----
render_buy_now_section(vn_copy)

# ---- Pro waitlist (email-gated; no public payment in beta) ----
st.markdown("---")
st.subheader(WAITLIST_HEADER)
st.markdown(WAITLIST_INTRO)

with st.form("pro_waitlist_form", clear_on_submit=False):
    waitlist_email = st.text_input(
        WAITLIST_EMAIL_LABEL,
        placeholder=WAITLIST_EMAIL_PLACEHOLDER,
        key="pro_waitlist_email",
    )
    submitted = st.form_submit_button(WAITLIST_BUTTON, type="primary")
    if submitted:
        if not waitlist_email.strip():
            st.warning("Vui lòng nhập email.")
        elif not is_valid_email(waitlist_email):
            st.error("Email không hợp lệ. Kiểm tra lại định dạng.")
        else:
            result = capture_lead(
                email=waitlist_email,
                tier="Pro Monthly",
                source_page="Soi Van Ban",
                notify_telegram=True,
            )
            if result.ok and not result.duplicate:
                st.success(result.message)
            elif result.ok and result.duplicate:
                st.info(result.message)
            else:
                st.error(result.message)

st.caption(WAITLIST_PRIVACY)

# ---- Footer ----
st.markdown("---")
st.markdown(LIMITATION_NOTE)
st.markdown(PRIVACY_NOTE)
st.markdown(BRAND_FRAME_VN)
