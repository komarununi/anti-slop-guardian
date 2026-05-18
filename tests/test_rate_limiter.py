"""Rate limiter tests — sliding-window counter, per-scope/key isolation."""

import sys
import time
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from rate_limiter import (
    DEFAULT_POLICIES,
    RateLimitResult,
    check, reset, prune_old, get_stats,
    _hash_key,
)


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / 'test_ratelimiter.db'


# ============================================================
# Key hashing (privacy)
# ============================================================


class TestKeyHash:
    def test_deterministic(self):
        assert _hash_key('192.0.2.1') == _hash_key('192.0.2.1')

    def test_different_keys_different_hashes(self):
        assert _hash_key('192.0.2.1') != _hash_key('192.0.2.2')

    def test_truncated_16_chars(self):
        h = _hash_key('any-key')
        assert len(h) == 16

    def test_empty_returns_unknown(self):
        assert _hash_key('') == 'unknown'

    def test_raw_key_not_in_hash(self):
        # Hash should not contain the original key
        h = _hash_key('192.0.2.1')
        assert '192.0.2.1' not in h


# ============================================================
# Basic allow / deny
# ============================================================


class TestBasicCheck:
    def test_first_request_allowed(self, tmp_db):
        result = check('generic_per_ip_minute', '192.0.2.1', db_path=tmp_db)
        assert result.allowed is True
        assert result.current_count == 1

    def test_within_limit_allowed(self, tmp_db):
        for i in range(5):
            result = check('llm_layer3_per_session', 'sess-1',
                          limit=10, window_seconds=60, db_path=tmp_db)
            assert result.allowed is True

    def test_exceeds_limit_denied(self, tmp_db):
        # Hit limit
        for _ in range(3):
            check('landing_demo_per_ip', '192.0.2.1',
                  limit=3, window_seconds=60, db_path=tmp_db)
        # 4th should fail
        result = check('landing_demo_per_ip', '192.0.2.1',
                      limit=3, window_seconds=60, db_path=tmp_db)
        assert result.allowed is False
        assert result.current_count == 3
        assert result.retry_after_seconds > 0


# ============================================================
# Scope + key isolation
# ============================================================


class TestIsolation:
    def test_different_scopes_independent(self, tmp_db):
        # Hit limit in scope A
        for _ in range(3):
            check('landing_demo_per_ip', '192.0.2.1',
                  limit=3, window_seconds=60, db_path=tmp_db)
        # Scope B unaffected
        result = check('llm_layer3_per_session', '192.0.2.1',
                      limit=10, db_path=tmp_db)
        assert result.allowed is True

    def test_different_keys_independent(self, tmp_db):
        # IP 1 hits limit
        for _ in range(3):
            check('landing_demo_per_ip', '192.0.2.1',
                  limit=3, window_seconds=60, db_path=tmp_db)
        # IP 2 unaffected
        result = check('landing_demo_per_ip', '192.0.2.2',
                      limit=3, window_seconds=60, db_path=tmp_db)
        assert result.allowed is True


# ============================================================
# Default policy lookup
# ============================================================


class TestDefaultPolicies:
    def test_landing_demo_default(self, tmp_db):
        # Default: 3 per day
        for i in range(3):
            r = check('landing_demo_per_ip', '192.0.2.10', db_path=tmp_db)
            assert r.allowed is True
            assert r.limit == 3
            assert r.window_seconds == 86400
        # 4th denied
        r = check('landing_demo_per_ip', '192.0.2.10', db_path=tmp_db)
        assert r.allowed is False

    def test_llm_layer3_default(self, tmp_db):
        r = check('llm_layer3_per_session', 'sess-1', db_path=tmp_db)
        assert r.limit == 50
        assert r.window_seconds == 3600

    def test_unknown_scope_uses_fallback(self, tmp_db):
        r = check('some_unknown_scope', 'k1', db_path=tmp_db)
        # Falls back to (60, 60)
        assert r.allowed is True
        assert r.limit == 60


# ============================================================
# Peek mode (increment_on_allow=False)
# ============================================================


class TestPeek:
    def test_peek_does_not_increment(self, tmp_db):
        # Peek 10 times — should never trip
        for _ in range(10):
            r = check('landing_demo_per_ip', '192.0.2.50',
                      limit=3, increment_on_allow=False, db_path=tmp_db)
            assert r.allowed is True
            assert r.current_count == 0  # never incremented


# ============================================================
# Window expiry
# ============================================================


class TestWindowExpiry:
    def test_window_expiry_clears_count(self, tmp_db):
        # Trip with short window
        for _ in range(2):
            check('test_scope', 'k1', limit=2, window_seconds=1, db_path=tmp_db)
        # Verify denied
        r = check('test_scope', 'k1', limit=2, window_seconds=1, db_path=tmp_db)
        assert r.allowed is False

        # Wait for window to expire
        time.sleep(1.2)

        # Should be allowed again
        r = check('test_scope', 'k1', limit=2, window_seconds=1, db_path=tmp_db)
        assert r.allowed is True


# ============================================================
# Reset + admin
# ============================================================


class TestReset:
    def test_reset_clears_counters(self, tmp_db):
        for _ in range(3):
            check('landing_demo_per_ip', '192.0.2.1',
                  limit=3, db_path=tmp_db)
        # At limit
        assert check('landing_demo_per_ip', '192.0.2.1',
                    limit=3, increment_on_allow=False, db_path=tmp_db).current_count == 3

        # Reset
        deleted = reset('landing_demo_per_ip', '192.0.2.1', db_path=tmp_db)
        assert deleted == 3

        # Fresh start
        r = check('landing_demo_per_ip', '192.0.2.1',
                 limit=3, db_path=tmp_db)
        assert r.allowed is True
        assert r.current_count == 1


class TestPruneOld:
    def test_prunes_old_rows(self, tmp_db):
        # Insert manually with old timestamp
        import sqlite3
        conn = sqlite3.connect(str(tmp_db))
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS rate_limit_counters (
                scope TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
        ''')
        old_time = time.time() - 10_000_000  # ~115 days ago
        conn.execute(
            'INSERT INTO rate_limit_counters VALUES (?, ?, ?)',
            ('scope1', 'key1', old_time),
        )
        conn.commit()
        conn.close()

        deleted = prune_old(older_than_seconds=86400, db_path=tmp_db)
        assert deleted == 1


# ============================================================
# Stats
# ============================================================


class TestStats:
    def test_stats_returns_count(self, tmp_db):
        for _ in range(5):
            check('landing_demo_per_ip', '192.0.2.1',
                  limit=10, db_path=tmp_db)
        stats = get_stats('landing_demo_per_ip', '192.0.2.1', db_path=tmp_db)
        assert stats['count_in_window'] == 5


# ============================================================
# Retry-after calculation
# ============================================================


class TestRetryAfter:
    def test_retry_after_within_window(self, tmp_db):
        # Trip limit
        for _ in range(3):
            check('test_window', 'k1', limit=3, window_seconds=60, db_path=tmp_db)

        r = check('test_window', 'k1', limit=3, window_seconds=60, db_path=tmp_db)
        assert r.allowed is False
        # retry_after should be positive, ≤ window
        assert 0 < r.retry_after_seconds <= 60
