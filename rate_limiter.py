"""Generic rate limiter — sliding window counter, SQLite-backed.

Per SVB threat model v2 Task #5. Two use cases:

1. **Layer-3 LLM call cap** (per session, cost protection)
   Even paid users shouldn't hammer Claude API; default 50/session.

2. **Landing demo per-IP** (per IP per day)
   Free demo gated to 3 analyses/IP/24h to prevent abuse of unpaid surface.

Pattern: every privileged action calls `rate_limiter.check(scope, key)`.
Returns RateLimitResult. Caller decides whether to throttle/refuse.

AppSec build 2026-05-19 marathon Task #5.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from license_db import _connect

# Default policies (override via check() args)
DEFAULT_POLICIES = {
    'llm_layer3_per_session': {'limit': 50, 'window_seconds': 3600},     # 50/hour/session
    'landing_demo_per_ip': {'limit': 3, 'window_seconds': 86400},        # 3/day/IP
    'generic_per_ip_minute': {'limit': 60, 'window_seconds': 60},        # 60/min/IP
}


@dataclass
class RateLimitResult:
    """Outcome of rate limit check."""
    allowed: bool
    current_count: int          # how many requests in current window (post-this-one if allowed)
    limit: int                  # max allowed in window
    window_seconds: int
    retry_after_seconds: int    # 0 if allowed, else seconds until next slot
    scope: str
    key_hash: str               # hashed identifier (privacy)


def _hash_key(key: str) -> str:
    """Hash arbitrary key (IP, session_id) for storage privacy."""
    if not key:
        return 'unknown'
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Idempotent rate_limit_counters table."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS rate_limit_counters (
            scope        TEXT NOT NULL,
            key_hash     TEXT NOT NULL,
            timestamp    REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rl_scope_key_time
            ON rate_limit_counters(scope, key_hash, timestamp);
        CREATE INDEX IF NOT EXISTS idx_rl_timestamp ON rate_limit_counters(timestamp);
    ''')
    conn.commit()


def check(
    scope: str,
    key: str,
    limit: Optional[int] = None,
    window_seconds: Optional[int] = None,
    increment_on_allow: bool = True,
    db_path: Optional[Path] = None,
) -> RateLimitResult:
    """Check + (optionally) record rate-limited action.

    Args:
        scope: Policy scope name (e.g. 'llm_layer3_per_session', 'landing_demo_per_ip').
               If matches DEFAULT_POLICIES, default limit/window used.
        key: Identifier (IP, session_id, license_key, etc). Hashed for storage.
        limit: Override scope's default limit.
        window_seconds: Override scope's default window.
        increment_on_allow: If True, record this attempt when allowed (default).
                           If False, just check without recording (peek).
        db_path: Override DB path (test only).

    Returns RateLimitResult. caller checks `.allowed` to throttle.
    """
    policy = DEFAULT_POLICIES.get(scope, {})
    effective_limit = limit if limit is not None else policy.get('limit', 60)
    effective_window = window_seconds if window_seconds is not None else policy.get('window_seconds', 60)
    key_h = _hash_key(key)

    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        now = time.time()
        window_start = now - effective_window

        # Count attempts in window
        current_count = conn.execute(
            'SELECT COUNT(*) FROM rate_limit_counters '
            'WHERE scope = ? AND key_hash = ? AND timestamp > ?',
            (scope, key_h, window_start),
        ).fetchone()[0]

        if current_count >= effective_limit:
            # Compute retry_after: find oldest hit in window, retry when it ages out
            oldest = conn.execute(
                'SELECT MIN(timestamp) FROM rate_limit_counters '
                'WHERE scope = ? AND key_hash = ? AND timestamp > ?',
                (scope, key_h, window_start),
            ).fetchone()[0]
            retry_after = max(1, int(oldest + effective_window - now)) if oldest else effective_window
            return RateLimitResult(
                allowed=False,
                current_count=current_count,
                limit=effective_limit,
                window_seconds=effective_window,
                retry_after_seconds=retry_after,
                scope=scope,
                key_hash=key_h,
            )

        if increment_on_allow:
            conn.execute(
                'INSERT INTO rate_limit_counters (scope, key_hash, timestamp) '
                'VALUES (?, ?, ?)',
                (scope, key_h, now),
            )
            conn.commit()
            current_count += 1

        return RateLimitResult(
            allowed=True,
            current_count=current_count,
            limit=effective_limit,
            window_seconds=effective_window,
            retry_after_seconds=0,
            scope=scope,
            key_hash=key_h,
        )
    finally:
        conn.close()


def reset(
    scope: str,
    key: str,
    db_path: Optional[Path] = None,
) -> int:
    """Clear all counters for a (scope, key) — useful for tests + admin override.

    Returns number of rows deleted.
    """
    key_h = _hash_key(key)
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        cur = conn.execute(
            'DELETE FROM rate_limit_counters WHERE scope = ? AND key_hash = ?',
            (scope, key_h),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def prune_old(
    older_than_seconds: int = 86400 * 7,
    db_path: Optional[Path] = None,
) -> int:
    """Delete counter rows older than threshold (default 7 days). Returns rows deleted.

    Should run as scheduled task (weekly) to prevent unbounded growth.
    """
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        cutoff = time.time() - older_than_seconds
        cur = conn.execute(
            'DELETE FROM rate_limit_counters WHERE timestamp < ?',
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_stats(
    scope: str,
    key: str,
    window_seconds: int = 3600,
    db_path: Optional[Path] = None,
) -> dict:
    """Read-only stats for monitoring/dashboard."""
    key_h = _hash_key(key)
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        window_start = time.time() - window_seconds
        count = conn.execute(
            'SELECT COUNT(*) FROM rate_limit_counters '
            'WHERE scope = ? AND key_hash = ? AND timestamp > ?',
            (scope, key_h, window_start),
        ).fetchone()[0]
        return {
            'scope': scope,
            'key_hash': key_h,
            'count_in_window': count,
            'window_seconds': window_seconds,
        }
    finally:
        conn.close()
