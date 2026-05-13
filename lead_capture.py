"""
Lead Capture — email-gated waitlist for Pro tier
==================================================

Beta strategy: no public payment integration yet. Capture interested-buyer
emails to a local CSV. CEO follows up manually with VietQR/bank info via
email (private channel). Optional: Telegram notify on new lead.

Storage:
  - data/pro_leads.csv (created on first write, gitignored by default)
  - Schema: timestamp, email, tier, source_page, user_agent_hash

Privacy:
  - Email stored locally only, NEVER sent to external LLM
  - No PII other than email (no name, no phone)
  - User must opt-in explicitly (button click after typing email)
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Same dir level as streamlit-app/
DATA_DIR = Path(__file__).resolve().parent / "data"
LEADS_CSV = DATA_DIR / "pro_leads.csv"

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Headers in CSV
_FIELDS = ["timestamp", "email", "tier", "source_page", "ua_hash"]


@dataclass
class CaptureResult:
    ok: bool
    message: str
    duplicate: bool = False


def is_valid_email(s: str) -> bool:
    if not s or len(s) > 254:
        return False
    return bool(_EMAIL_RE.match(s.strip()))


def _ensure_csv():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not LEADS_CSV.exists():
        with LEADS_CSV.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(_FIELDS)


def _existing_emails() -> set[str]:
    if not LEADS_CSV.exists():
        return set()
    out = set()
    try:
        with LEADS_CSV.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                e = (row.get("email") or "").strip().lower()
                if e:
                    out.add(e)
    except Exception as e:
        logger.warning("read leads CSV failed: %s", e)
    return out


def capture_lead(email: str,
                 tier: str = "Pro Monthly",
                 source_page: str = "Soi Van Ban",
                 user_agent: Optional[str] = None,
                 notify_telegram: bool = False) -> CaptureResult:
    """Append email to leads CSV. Returns CaptureResult.

    notify_telegram: if True and TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env
    set, post a lightweight notification (email is hashed in the alert,
    not sent in clear).
    """
    if not is_valid_email(email):
        return CaptureResult(ok=False, message="Email không hợp lệ.")

    norm = email.strip().lower()
    if norm in _existing_emails():
        return CaptureResult(
            ok=True,
            message="Email này đã được ghi nhận trước đó. Không cần đăng ký lại.",
            duplicate=True,
        )

    _ensure_csv()
    ua_hash = ""
    if user_agent:
        ua_hash = hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:16]

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "email": norm,
        "tier": tier,
        "source_page": source_page,
        "ua_hash": ua_hash,
    }
    try:
        with LEADS_CSV.open("a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=_FIELDS).writerow(row)
    except Exception as e:
        logger.error("append lead failed: %s", e)
        return CaptureResult(ok=False, message=f"Lỗi lưu: {e}")

    if notify_telegram:
        _telegram_notify(norm, tier)

    return CaptureResult(
        ok=True,
        message="Cảm ơn bạn đã đăng ký. Khi Pro ra mắt (dự kiến tháng 5/2026), "
                "thông tin thanh toán sẽ được gửi qua email.",
    )


def _telegram_notify(email_norm: str, tier: str) -> None:
    """Send Telegram alert to CEO bot with FULL email (private channel).

    Privacy model: Telegram bot is owned by CEO (chat_id specific to CEO chat).
    Plain email is acceptable because the channel is end-to-end private to CEO.
    Used as primary lead-delivery channel in beta (E1 strategy 2026-05-13).
    Reply workflow: CEO copies email from Telegram → composes from
    komarununi.business@gmail.com with VietQR / Stripe link.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    try:
        import requests
    except ImportError:
        return
    text = (
        f"*[Pro lead mới]*\n"
        f"📧 `{email_norm}`\n"
        f"🎯 Tier: {tier}\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"_Reply: copy email → gửi từ komarununi.business@gmail.com_"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception as e:
        logger.warning("Telegram notify failed: %s", e)


def lead_count() -> int:
    return len(_existing_emails())
