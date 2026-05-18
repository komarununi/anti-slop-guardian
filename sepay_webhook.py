"""SEPay webhook handler for SVB payment → license auto-issuance.

Per SVB threat model v2 Q6: webhook MUST validate HMAC signature before
trusting payment notification. Without HMAC, attacker forges fake payment
events → free license issuance.

Architecture:
- This module is FRAMEWORK-AGNOSTIC. Provides verify + handler functions.
- Caller (FastAPI/Flask/Streamlit-Cloud webhook adapter) wires HTTP layer.
- Pattern from komaru-marketing/.claude/skills/payment-integration/references/sepay/.

Security properties:
- HMAC-SHA256 signature verification (timing-safe via hmac.compare_digest)
- Replay protection via transaction_id deduplication
- Idempotent: same transaction_id processed only once
- Privacy: never logs full webhook payload (only essential fields)
- Fail-closed: missing secret, invalid signature → reject

AppSec build 2026-05-19 marathon Task #4.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from license_db import LICENSE_DB_DEFAULT, _connect, issue_license

logger = logging.getLogger(__name__)


# Min secret length for HMAC signing key (256-bit recommended)
MIN_SECRET_LENGTH = 32

# Pricing → plan mapping (VND)
# Per SVB current pricing: Pro $9 ≈ 220k VND, Bundle $39 ≈ 950k VND
PRICE_TO_PLAN_VND = {
    220000: 'pro',   # Pro $9/mo
    950000: 'bundle',  # Bundle $39 one-time
}
# Tolerance in VND for amount matching (FX fluctuation)
PRICE_TOLERANCE_VND = 5000


class WebhookError(Exception):
    """Base webhook error — always returned as 400/401 to caller."""


class HMACError(WebhookError):
    """HMAC signature mismatch — possible attack."""


class AlreadyProcessedError(WebhookError):
    """Transaction already processed — idempotent re-call."""


class UnknownAmountError(WebhookError):
    """Payment amount doesn't match any pricing tier."""


@dataclass
class WebhookResult:
    """Outcome of webhook processing."""
    success: bool
    license_key: Optional[str] = None
    plan: Optional[str] = None
    email: Optional[str] = None
    transaction_id: Optional[str] = None
    error: Optional[str] = None


def verify_hmac(
    payload: bytes,
    received_signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature using timing-safe compare.

    Args:
        payload: Raw request body as bytes (NOT parsed JSON — must be raw
                 bytes so HMAC matches what SEPay signed).
        received_signature: Header value sent by SEPay (hex digest).
        secret: Shared secret key (from SEPAY_WEBHOOK_SECRET env var).

    Returns: True if signature valid AND secret long enough. False otherwise.

    Privacy: never logs payload content or signature value.
    """
    if not secret or len(secret) < MIN_SECRET_LENGTH:
        logger.error('SEPAY_WEBHOOK_SECRET missing or too short')
        return False
    if not received_signature:
        return False
    # Normalize: SEPay may send hex with or without "sha256=" prefix
    sig_clean = received_signature.lower().replace('sha256=', '').strip()
    if not re.fullmatch(r'[a-f0-9]{64}', sig_clean):
        return False  # malformed signature
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256,
    ).hexdigest()
    # Timing-safe comparison
    return hmac.compare_digest(expected, sig_clean)


def _ensure_dedup_table(conn: sqlite3.Connection) -> None:
    """Idempotency table — prevent replay of same SEPay transaction."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS processed_transactions (
            transaction_id  TEXT PRIMARY KEY NOT NULL,
            processed_at    REAL NOT NULL,
            license_key     TEXT,
            amount_vnd      INTEGER
        )
    ''')
    conn.commit()


def _is_duplicate_transaction(
    conn: sqlite3.Connection,
    transaction_id: str,
) -> Optional[str]:
    """Return existing license_key if transaction already processed."""
    row = conn.execute(
        'SELECT license_key FROM processed_transactions WHERE transaction_id = ?',
        (transaction_id,),
    ).fetchone()
    return row[0] if row else None


def _record_processed(
    conn: sqlite3.Connection,
    transaction_id: str,
    license_key: str,
    amount_vnd: int,
) -> None:
    conn.execute(
        'INSERT INTO processed_transactions '
        '(transaction_id, processed_at, license_key, amount_vnd) '
        'VALUES (?, ?, ?, ?)',
        (transaction_id, time.time(), license_key, amount_vnd),
    )
    conn.commit()


def _resolve_plan(amount_vnd: int) -> Optional[str]:
    """Match payment amount to plan within tolerance."""
    for price, plan in PRICE_TO_PLAN_VND.items():
        if abs(amount_vnd - price) <= PRICE_TOLERANCE_VND:
            return plan
    return None


def _extract_email_from_content(content: Optional[str]) -> Optional[str]:
    """Extract email from SEPay transfer content / memo field.

    Buyers include email in transfer memo per SVB buy flow instructions.
    Pattern: extract first email-like string from content.
    """
    if not content:
        return None
    match = re.search(
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        content,
    )
    return match.group(0).lower().strip() if match else None


def handle_payment_event(
    event: dict,
    db_path: Optional[Path] = None,
) -> WebhookResult:
    """Process a verified SEPay webhook event.

    Pre-condition: HMAC already verified by caller via verify_hmac().

    Expected event shape (per SEPay docs):
    {
        "id": <int>,
        "transaction_id": <str>,
        "gateway": <str>,
        "transactionDate": <str>,
        "accountNumber": <str>,
        "subAccount": <str>,
        "amountIn": <int>,           // VND amount received
        "amountOut": 0,
        "accumulated": <int>,
        "code": <str>,                // payment code (optional)
        "transactionContent": <str>,  // memo from sender (contains email)
        "referenceNumber": <str>,
        "description": <str>
    }

    Returns WebhookResult — if success=True, license_key is the newly issued key.
    """
    transaction_id = str(event.get('transaction_id') or event.get('id') or '')
    amount_vnd = int(event.get('amountIn', 0) or 0)
    content = event.get('transactionContent') or event.get('description') or ''

    if not transaction_id:
        return WebhookResult(success=False, error='missing transaction_id')
    if amount_vnd <= 0:
        return WebhookResult(success=False, error='non-positive amount')

    # Resolve plan from amount
    plan = _resolve_plan(amount_vnd)
    if not plan:
        return WebhookResult(
            success=False,
            error=f'amount {amount_vnd} VND does not match any pricing tier',
            transaction_id=transaction_id,
        )

    # Extract email from transfer memo
    email = _extract_email_from_content(content)
    if not email:
        return WebhookResult(
            success=False,
            error='no email found in transactionContent (buyer must include email in memo)',
            transaction_id=transaction_id,
        )

    # Idempotency check
    conn = _connect(db_path)
    try:
        _ensure_dedup_table(conn)
        existing_key = _is_duplicate_transaction(conn, transaction_id)
        if existing_key:
            return WebhookResult(
                success=True,  # idempotent — return prior result
                license_key=existing_key,
                plan=plan,
                email=email,
                transaction_id=transaction_id,
                error=None,
            )

        # Issue new license
        license_key = issue_license(
            email=email,
            plan=plan,
            payment_ref=f'sepay:{transaction_id}',
            db_path=db_path,
        )
        _record_processed(conn, transaction_id, license_key, amount_vnd)

        # Privacy-safe log (no full key, only prefix)
        logger.info(
            'Payment processed: txn=%s plan=%s email_domain=%s license=KMR-%s***',
            transaction_id[:12],
            plan,
            email.split('@')[-1] if '@' in email else '?',
            license_key[4:12],
        )

        return WebhookResult(
            success=True,
            license_key=license_key,
            plan=plan,
            email=email,
            transaction_id=transaction_id,
        )
    finally:
        conn.close()


def process_webhook(
    payload: bytes,
    received_signature: str,
    secret: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> WebhookResult:
    """Top-level entry: verify HMAC + parse JSON + issue license.

    This is what HTTP framework (FastAPI/Flask/etc) calls. Returns
    WebhookResult — caller maps to HTTP 200 (success) or 4xx (error).

    Args:
        payload: Raw request body bytes (DO NOT pre-parse JSON).
        received_signature: 'X-Signature' or similar header from SEPay.
        secret: HMAC secret. Defaults to SEPAY_WEBHOOK_SECRET env var.
        db_path: Override DB location (test only).
    """
    secret = secret or os.environ.get('SEPAY_WEBHOOK_SECRET', '')
    if not secret:
        logger.error('SEPAY_WEBHOOK_SECRET env var not set — refusing webhook')
        return WebhookResult(success=False, error='server misconfigured (no secret)')

    if not verify_hmac(payload, received_signature, secret):
        logger.warning('Webhook signature invalid — possible attack')
        return WebhookResult(success=False, error='invalid signature')

    try:
        event = json.loads(payload.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return WebhookResult(success=False, error=f'invalid JSON: {e}')

    if not isinstance(event, dict):
        return WebhookResult(success=False, error='event must be JSON object')

    return handle_payment_event(event, db_path=db_path)
