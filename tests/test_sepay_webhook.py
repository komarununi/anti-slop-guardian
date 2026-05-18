"""SEPay webhook handler tests — HMAC verify + license auto-issuance."""

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from sepay_webhook import (
    MIN_SECRET_LENGTH, PRICE_TO_PLAN_VND, PRICE_TOLERANCE_VND,
    verify_hmac, handle_payment_event, process_webhook,
    _extract_email_from_content, _resolve_plan,
)


VALID_SECRET = 'a' * MIN_SECRET_LENGTH + '_extra_padding'


def sign(payload: bytes, secret: str = VALID_SECRET) -> str:
    """Compute HMAC-SHA256 hex digest for payload."""
    return hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / 'test_licenses.db'


# ============================================================
# HMAC verification
# ============================================================


class TestVerifyHMAC:
    def test_valid_signature_passes(self):
        payload = b'{"transaction_id":"123","amountIn":220000}'
        sig = sign(payload)
        assert verify_hmac(payload, sig, VALID_SECRET) is True

    def test_accepts_sha256_prefix(self):
        payload = b'{"x":1}'
        sig = 'sha256=' + sign(payload)
        assert verify_hmac(payload, sig, VALID_SECRET) is True

    def test_wrong_signature_rejected(self):
        payload = b'{"transaction_id":"123"}'
        assert verify_hmac(payload, 'a' * 64, VALID_SECRET) is False

    def test_empty_signature_rejected(self):
        assert verify_hmac(b'{"x":1}', '', VALID_SECRET) is False

    def test_malformed_signature_rejected(self):
        # Not hex
        assert verify_hmac(b'{"x":1}', 'ZZZZ', VALID_SECRET) is False

    def test_too_short_secret_rejected(self):
        payload = b'{"x":1}'
        weak_secret = 'short'
        sig = sign(payload, weak_secret)
        # Even with valid sig FOR the weak secret, function rejects
        assert verify_hmac(payload, sig, weak_secret) is False

    def test_empty_secret_rejected(self):
        assert verify_hmac(b'{"x":1}', sign(b'{"x":1}'), '') is False

    def test_payload_tampering_detected(self):
        original = b'{"amountIn":220000}'
        tampered = b'{"amountIn":1}'
        sig = sign(original)
        # Tampered payload should not validate
        assert verify_hmac(tampered, sig, VALID_SECRET) is False


# ============================================================
# Email extraction
# ============================================================


class TestEmailExtraction:
    def test_finds_simple_email(self):
        assert _extract_email_from_content(
            'Payment for SVB Pro buyer@example.com thanks'
        ) == 'buyer@example.com'

    def test_normalizes_lowercase(self):
        assert _extract_email_from_content(
            'Buyer@Example.COM'
        ) == 'buyer@example.com'

    def test_returns_none_no_email(self):
        assert _extract_email_from_content('Just a transfer note') is None
        assert _extract_email_from_content('') is None
        assert _extract_email_from_content(None) is None

    def test_first_email_wins(self):
        result = _extract_email_from_content('one@a.com and two@b.com')
        assert result == 'one@a.com'


# ============================================================
# Plan resolution from amount
# ============================================================


class TestPlanResolution:
    def test_exact_pro_amount(self):
        assert _resolve_plan(220000) == 'pro'

    def test_exact_bundle_amount(self):
        assert _resolve_plan(950000) == 'bundle'

    def test_pro_within_tolerance(self):
        assert _resolve_plan(220000 + PRICE_TOLERANCE_VND) == 'pro'
        assert _resolve_plan(220000 - PRICE_TOLERANCE_VND) == 'pro'

    def test_outside_tolerance_returns_none(self):
        assert _resolve_plan(220000 + PRICE_TOLERANCE_VND + 1) is None
        assert _resolve_plan(100000) is None
        assert _resolve_plan(1000000) is None


# ============================================================
# Handle payment event
# ============================================================


def make_event(**overrides) -> dict:
    """Helper to build SEPay-shaped event."""
    base = {
        'transaction_id': 'TXN-001',
        'amountIn': 220000,
        'transactionContent': 'SVB Pro buyer@example.com',
    }
    base.update(overrides)
    return base


class TestHandlePaymentEvent:
    def test_pro_payment_issues_license(self, tmp_db):
        result = handle_payment_event(make_event(), db_path=tmp_db)
        assert result.success is True
        assert result.plan == 'pro'
        assert result.email == 'buyer@example.com'
        assert result.license_key is not None
        assert result.license_key.startswith('KMR-')

    def test_bundle_payment(self, tmp_db):
        result = handle_payment_event(
            make_event(amountIn=950000, transaction_id='TXN-002'),
            db_path=tmp_db,
        )
        assert result.success is True
        assert result.plan == 'bundle'

    def test_unknown_amount_rejected(self, tmp_db):
        result = handle_payment_event(
            make_event(amountIn=99999),
            db_path=tmp_db,
        )
        assert result.success is False
        assert 'pricing tier' in result.error.lower()

    def test_no_email_rejected(self, tmp_db):
        result = handle_payment_event(
            make_event(transactionContent='no email here'),
            db_path=tmp_db,
        )
        assert result.success is False
        assert 'email' in result.error.lower()

    def test_zero_amount_rejected(self, tmp_db):
        result = handle_payment_event(
            make_event(amountIn=0),
            db_path=tmp_db,
        )
        assert result.success is False
        assert 'amount' in result.error.lower()

    def test_idempotent_replay(self, tmp_db):
        """Same transaction_id → same license, not double-issued."""
        result1 = handle_payment_event(make_event(), db_path=tmp_db)
        result2 = handle_payment_event(make_event(), db_path=tmp_db)
        assert result1.success is True
        assert result2.success is True
        assert result1.license_key == result2.license_key


# ============================================================
# End-to-end process_webhook (HMAC + handler combined)
# ============================================================


class TestProcessWebhook:
    def test_e2e_success(self, tmp_db):
        event = make_event(transaction_id='E2E-001')
        payload = json.dumps(event).encode('utf-8')
        sig = sign(payload)
        result = process_webhook(payload, sig, secret=VALID_SECRET, db_path=tmp_db)
        assert result.success is True
        assert result.license_key.startswith('KMR-')

    def test_e2e_bad_signature(self, tmp_db):
        payload = json.dumps(make_event()).encode('utf-8')
        result = process_webhook(
            payload, 'a' * 64, secret=VALID_SECRET, db_path=tmp_db,
        )
        assert result.success is False
        assert 'signature' in result.error.lower()

    def test_e2e_no_secret_configured(self, tmp_db):
        payload = json.dumps(make_event()).encode('utf-8')
        sig = sign(payload, secret='dummy_doesnt_matter')
        result = process_webhook(payload, sig, secret='', db_path=tmp_db)
        assert result.success is False
        assert 'misconfigured' in result.error.lower()

    def test_e2e_invalid_json(self, tmp_db):
        payload = b'not valid json {{{'
        sig = sign(payload)
        result = process_webhook(payload, sig, secret=VALID_SECRET, db_path=tmp_db)
        assert result.success is False
        assert 'json' in result.error.lower()

    def test_e2e_non_dict_payload(self, tmp_db):
        payload = b'["array", "not", "object"]'
        sig = sign(payload)
        result = process_webhook(payload, sig, secret=VALID_SECRET, db_path=tmp_db)
        assert result.success is False
        assert 'json object' in result.error.lower()
