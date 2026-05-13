"""Buy-Now section helper for W2 manual launch.

Renders a Telegram-DM CTA + email fallback. Shared between main.py (EN)
and pages/2_Soi_Van_Ban.py (VN).

W2 manual workflow per Business Council 2026-05-14 #2 — Telegram-first,
Sepay W3 trigger ≥5 sales, Stripe W4 trigger ≥15 sales/month.

Telegram URL format: https://t.me/<HANDLE>?text=<URL_ENCODED_PREFILL>
- Handle from env `KOMARU_BUY_TG_HANDLE` (CEO sets pre-launch)
- Fallback: email link to komarununi.business@gmail.com
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus

import streamlit as st


def _telegram_url(handle: str, prefill: str) -> str:
    return f"https://t.me/{handle}?text={quote_plus(prefill)}"


def render_buy_now_section(copy_module) -> None:
    """Render the Buy-Now CTA using strings from a copy module.

    copy_module: must expose BUY_NOW_HEADER, BUY_NOW_INTRO,
    BUY_NOW_BUNDLE_NAME, BUY_NOW_BUNDLE_PRICE_VND, BUY_NOW_BUNDLE_PRICE_USD,
    BUY_NOW_BUNDLE_DESC, BUY_NOW_BUTTON_LABEL, BUY_NOW_PREFILL,
    BUY_NOW_FALLBACK, BUY_NOW_FOOTNOTE.
    """
    handle = os.environ.get("KOMARU_BUY_TG_HANDLE", "").strip()
    tg_url = _telegram_url(handle, copy_module.BUY_NOW_PREFILL) if handle else None

    st.markdown("---")
    st.subheader(copy_module.BUY_NOW_HEADER)
    st.markdown(copy_module.BUY_NOW_INTRO)

    st.markdown(
        f"""
        <div style='border:2px solid #0F2A47;padding:1.2rem;border-radius:8px;
                    background:#f8fafc;margin:1rem 0;'>
          <div style='font-weight:700;color:#0F2A47;font-size:1.15rem;'>
            {copy_module.BUY_NOW_BUNDLE_NAME}
          </div>
          <div style='color:#dc2626;font-weight:700;font-size:1.4rem;
                      margin:0.4rem 0;'>
            {copy_module.BUY_NOW_BUNDLE_PRICE_VND}
            <span style='color:#64748b;font-size:0.95rem;font-weight:500;'>
              · {copy_module.BUY_NOW_BUNDLE_PRICE_USD}
            </span>
          </div>
          <div style='color:#374151;font-size:0.9rem;margin-top:0.5rem;'>
            {copy_module.BUY_NOW_BUNDLE_DESC}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if tg_url:
        st.link_button(copy_module.BUY_NOW_BUTTON_LABEL, tg_url,
                       type="primary", use_container_width=False)
    else:
        st.warning(
            "Telegram handle chưa cấu hình. "
            "Set env `KOMARU_BUY_TG_HANDLE` trước khi launch W2."
        )

    st.caption(copy_module.BUY_NOW_FALLBACK)
    st.caption(copy_module.BUY_NOW_FOOTNOTE)
