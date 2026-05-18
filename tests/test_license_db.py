"""License DB tests — covers generation, validation, rate limiting, audit."""

import sys
import time
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from license_db import (
    LICENSE_KEY_PATTERN, RATE_LIMIT_MAX_FAILURES,
    ValidationResult,
    generate_license_key, issue_license, validate_license, revoke_license,
    get_recent_failures, _hash_ip, _key_prefix,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Isolated test DB per test."""
    return tmp_path / 'test_licenses.db'


# ============================================================
# Key generation
# ============================================================


class TestKeyGeneration:
    def test_format_matches_pattern(self):
        for _ in range(20):
            key = generate_license_key()
            assert LICENSE_KEY_PATTERN.match(key), f'Bad format: {key}'

    def test_keys_are_unique(self):
        keys = {generate_license_key() for _ in range(100)}
        assert len(keys) == 100  # collisions vanishingly unlikely

    def test_format_specifics(self):
        key = generate_license_key()
        assert key.startswith('KMR-')
        parts = key.split('-')
        assert len(parts) == 4  # KMR, segment1, segment2, segment3
        assert len(parts[1]) == 8
        assert len(parts[2]) == 4
        assert len(parts[3]) == 8


# ============================================================
# Issue (DB write)
# ============================================================


class TestIssueLicense:
    def test_issues_valid_key(self, tmp_db):
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        assert LICENSE_KEY_PATTERN.match(key)

    def test_validates_after_issue(self, tmp_db):
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        result = validate_license(key, ip='192.0.2.1', db_path=tmp_db)
        assert result.valid is True
        assert result.plan == 'pro'
        assert result.email == 'buyer@example.com'

    def test_rejects_invalid_plan(self, tmp_db):
        with pytest.raises(ValueError, match='plan must be'):
            issue_license('buyer@example.com', 'invalid_plan', db_path=tmp_db)

    def test_rejects_invalid_email(self, tmp_db):
        with pytest.raises(ValueError, match='invalid email'):
            issue_license('not-an-email', 'pro', db_path=tmp_db)

    def test_email_normalized_lowercase(self, tmp_db):
        key = issue_license('Buyer@Example.com', 'pro', db_path=tmp_db)
        result = validate_license(key, db_path=tmp_db)
        assert result.email == 'buyer@example.com'


# ============================================================
# Validation
# ============================================================


class TestValidate:
    def test_rejects_malformed_key(self, tmp_db):
        result = validate_license('not-a-license', ip='192.0.2.1', db_path=tmp_db)
        assert result.valid is False
        assert 'format' in result.reason.lower()

    def test_rejects_empty_key(self, tmp_db):
        result = validate_license('', ip='192.0.2.1', db_path=tmp_db)
        assert result.valid is False

    def test_rejects_unknown_key(self, tmp_db):
        # Format-valid but never issued
        result = validate_license(
            'KMR-AAAAAAAA-BBBB-CCCCCCCC',
            ip='192.0.2.1',
            db_path=tmp_db,
        )
        assert result.valid is False
        assert 'not found' in result.reason.lower()

    def test_rejects_revoked_key(self, tmp_db):
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        revoke_license(key, reason='refunded', db_path=tmp_db)
        result = validate_license(key, ip='192.0.2.1', db_path=tmp_db)
        assert result.valid is False
        assert 'refunded' in result.reason.lower()

    def test_bundle_plan_accepted(self, tmp_db):
        key = issue_license('buyer@example.com', 'bundle', db_path=tmp_db)
        result = validate_license(key, db_path=tmp_db)
        assert result.valid is True
        assert result.plan == 'bundle'


# ============================================================
# Rate limiting
# ============================================================


class TestRateLimit:
    def test_lockout_after_max_failures(self, tmp_db):
        # Trigger MAX_FAILURES bad attempts
        for _ in range(RATE_LIMIT_MAX_FAILURES + 1):
            validate_license('KMR-BADBADBA-DDDD-BADBADBA', ip='192.0.2.99', db_path=tmp_db)

        # Next attempt should be locked out (even with a real-looking key)
        result = validate_license(
            'KMR-AAAAAAAA-BBBB-CCCCCCCC',
            ip='192.0.2.99',
            db_path=tmp_db,
        )
        assert result.locked_out is True
        assert result.valid is False
        assert 'rate limit' in result.reason.lower()

    def test_different_ip_not_affected(self, tmp_db):
        # IP 1 trips lockout
        for _ in range(RATE_LIMIT_MAX_FAILURES + 1):
            validate_license('KMR-BADBADBA-DDDD-BADBADBA', ip='192.0.2.99', db_path=tmp_db)

        # IP 2 still OK
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        result = validate_license(key, ip='192.0.2.5', db_path=tmp_db)
        assert result.valid is True

    def test_failure_count_resets_for_new_ip(self, tmp_db):
        # IP 1 some failures
        for _ in range(5):
            validate_license('KMR-BADBADBA-DDDD-BADBADBA', ip='192.0.2.10', db_path=tmp_db)
        # IP 2 zero failures
        assert get_recent_failures('192.0.2.10', db_path=tmp_db) == 5
        assert get_recent_failures('192.0.2.20', db_path=tmp_db) == 0


# ============================================================
# Privacy / TIER 0
# ============================================================


class TestPrivacy:
    def test_ip_is_hashed(self):
        h1 = _hash_ip('192.0.2.1')
        h2 = _hash_ip('192.0.2.1')
        # Deterministic for same IP
        assert h1 == h2
        # But not the raw IP
        assert '192.0.2.1' not in h1
        # SHA-256 truncated to 16 chars
        assert len(h1) == 16

    def test_key_prefix_only_safe_amount(self):
        key = 'KMR-ABCDEFGH-IJKL-MNOPQRST'
        prefix = _key_prefix(key)
        # Safe to log: KMR-ABCDEFGH (12 chars) — no leak of suffix
        assert prefix == 'KMR-ABCDEFGH'
        assert 'IJKL' not in prefix
        assert 'MNOPQRST' not in prefix

    def test_key_prefix_handles_invalid(self):
        assert _key_prefix('') == '<invalid>'
        assert _key_prefix(None) == '<invalid>'
        assert _key_prefix('xx') == '<invalid>'


# ============================================================
# Audit log
# ============================================================


class TestAuditLog:
    def test_success_audit_logged(self, tmp_db):
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        validate_license(key, ip='192.0.2.1', db_path=tmp_db)
        validate_license(key, ip='192.0.2.1', db_path=tmp_db)
        # 0 failures expected
        assert get_recent_failures('192.0.2.1', db_path=tmp_db) == 0

    def test_failure_audit_logged(self, tmp_db):
        validate_license('KMR-XXXXXXXX-XXXX-XXXXXXXX', ip='192.0.2.1', db_path=tmp_db)
        validate_license('not-a-key', ip='192.0.2.1', db_path=tmp_db)
        assert get_recent_failures('192.0.2.1', db_path=tmp_db) >= 2


# ============================================================
# Revocation
# ============================================================


class TestRevoke:
    def test_revoke_existing_returns_true(self, tmp_db):
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        assert revoke_license(key, db_path=tmp_db) is True

    def test_revoke_nonexistent_returns_false(self, tmp_db):
        assert revoke_license('KMR-AAAAAAAA-BBBB-CCCCCCCC', db_path=tmp_db) is False

    def test_refunded_status_stored(self, tmp_db):
        key = issue_license('buyer@example.com', 'pro', db_path=tmp_db)
        revoke_license(key, reason='refunded', db_path=tmp_db)
        result = validate_license(key, db_path=tmp_db)
        assert 'refunded' in result.reason.lower()
