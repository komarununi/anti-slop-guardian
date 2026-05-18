"""License validation backend for SVB Pro/Bundle gating.

Per SVB threat model v2 Q2: server-side license check on every privileged
operation. SQLite-backed (lightweight, no external service required for V1).

Key features:
- License key generation: secrets.token_urlsafe → KMR-XXXXXXXX-XXXX-XXXXXXXX format
- Server-side validation: every Layer-3 LLM call must produce valid license
- Audit log: track validation attempts for brute-force detection
- Rate limit: lockout after N failed attempts per IP hash
- TIER 0 safe: NEVER logs full license key (only first 8 chars + hash)

AppSec build 2026-05-19 marathon Task #3.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Configuration constants
LICENSE_KEY_PATTERN = re.compile(r'^KMR-[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{8}$')
LICENSE_DB_DEFAULT = Path(__file__).resolve().parent / 'licenses.db'

# Rate limiting on validation attempts
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
RATE_LIMIT_MAX_FAILURES = 20      # 20 fails / IP / hour = lockout
RATE_LIMIT_LOCKOUT_SECONDS = 86400  # 24 hour lockout once tripped

# Plan tiers
VALID_PLANS = {'pro', 'bundle'}

# License key alphabet: uppercase letters + digits (base36, excluding
# confusing chars 0/O, 1/I would reduce ambiguity but full base36 here
# for compatibility with existing demo content KMR-Q3C2IWA4-XQSD-59ICO5BW)
_ALPHABET = string.ascii_uppercase + string.digits


@dataclass
class ValidationResult:
    """Result of license check — never includes the raw key."""
    valid: bool
    plan: Optional[str] = None      # 'pro' / 'bundle' / None
    email: Optional[str] = None     # email associated with license (for display)
    reason: Optional[str] = None    # rejection reason if not valid
    locked_out: bool = False        # True if IP rate-limited


def _hash_ip(ip: str) -> str:
    """Hash IP for audit log (don't log raw IPs — privacy)."""
    if not ip:
        return 'unknown'
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()[:16]


def _key_prefix(key: str) -> str:
    """Return safe prefix for logging (first 12 chars = KMR-XXXXXXXX)."""
    if not key or len(key) < 12:
        return '<invalid>'
    return key[:12]


def _gen_segment(length: int) -> str:
    """Generate cryptographically-random alphanumeric segment."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def generate_license_key() -> str:
    """Generate a new KMR-XXXXXXXX-XXXX-XXXXXXXX license key.

    Format: 26 chars total
    - "KMR-" prefix (4 chars)
    - 8 alphanumeric (36^8 ≈ 2.8e12)
    - "-" separator
    - 4 alphanumeric (36^4 ≈ 1.7e6)
    - "-" separator
    - 8 alphanumeric (36^8 ≈ 2.8e12)

    Total entropy: 36^20 ≈ 1.3e31 = brute-force infeasible.
    Format compatible with auto_demo_video.py demo content.
    """
    return f"KMR-{_gen_segment(8)}-{_gen_segment(4)}-{_gen_segment(8)}"


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open SQLite connection + ensure schema."""
    path = Path(db_path) if db_path else LICENSE_DB_DEFAULT
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute('PRAGMA foreign_keys = ON')
    # Schema (idempotent)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS licenses (
            license_key   TEXT PRIMARY KEY NOT NULL,
            email         TEXT NOT NULL,
            plan          TEXT NOT NULL CHECK (plan IN ('pro', 'bundle')),
            status        TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'refunded', 'revoked')),
            payment_ref   TEXT,
            created_at    REAL NOT NULL,
            last_used_at  REAL
        );

        CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email);
        CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);

        CREATE TABLE IF NOT EXISTS validation_audit (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     REAL NOT NULL,
            ip_hash       TEXT NOT NULL,
            key_prefix    TEXT NOT NULL,
            success       INTEGER NOT NULL,
            reason        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_ip_time
            ON validation_audit(ip_hash, timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_time ON validation_audit(timestamp);

        CREATE TABLE IF NOT EXISTS rate_limit_lockouts (
            ip_hash       TEXT PRIMARY KEY NOT NULL,
            locked_until  REAL NOT NULL,
            reason        TEXT
        );
    ''')
    conn.commit()
    return conn


def issue_license(
    email: str,
    plan: str,
    payment_ref: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    """Generate + persist a new license key. Returns the key.

    Caller (e.g. SEPay webhook handler) is responsible for verifying payment
    BEFORE calling this. This function only does the DB write.
    """
    if plan not in VALID_PLANS:
        raise ValueError(f'plan must be one of {VALID_PLANS}, got {plan!r}')
    if not email or '@' not in email:
        raise ValueError(f'invalid email: {email!r}')

    # Try up to 5 times in case of (vanishingly unlikely) collision
    conn = _connect(db_path)
    try:
        for _ in range(5):
            key = generate_license_key()
            try:
                conn.execute(
                    'INSERT INTO licenses (license_key, email, plan, '
                    'payment_ref, created_at) VALUES (?, ?, ?, ?, ?)',
                    (key, email.lower().strip(), plan, payment_ref, time.time()),
                )
                conn.commit()
                return key
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError('Could not generate unique license after 5 attempts')
    finally:
        conn.close()


def _is_locked_out(conn: sqlite3.Connection, ip_hash: str) -> bool:
    """Check if IP is currently locked out."""
    now = time.time()
    row = conn.execute(
        'SELECT locked_until FROM rate_limit_lockouts WHERE ip_hash = ?',
        (ip_hash,),
    ).fetchone()
    if not row:
        return False
    locked_until = row[0]
    if now > locked_until:
        # Lockout expired — clear it
        conn.execute(
            'DELETE FROM rate_limit_lockouts WHERE ip_hash = ?', (ip_hash,)
        )
        conn.commit()
        return False
    return True


def _check_rate_limit(conn: sqlite3.Connection, ip_hash: str) -> bool:
    """Returns True if IP within rate limit, False if exceeded.

    Counts failed validations in last RATE_LIMIT_WINDOW_SECONDS. If exceeded,
    creates lockout entry for RATE_LIMIT_LOCKOUT_SECONDS.
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    failure_count = conn.execute(
        'SELECT COUNT(*) FROM validation_audit '
        'WHERE ip_hash = ? AND success = 0 AND timestamp > ?',
        (ip_hash, window_start),
    ).fetchone()[0]

    if failure_count >= RATE_LIMIT_MAX_FAILURES:
        # Trip lockout
        conn.execute(
            'INSERT OR REPLACE INTO rate_limit_lockouts '
            '(ip_hash, locked_until, reason) VALUES (?, ?, ?)',
            (ip_hash, now + RATE_LIMIT_LOCKOUT_SECONDS,
             f'{failure_count} failures in {RATE_LIMIT_WINDOW_SECONDS}s'),
        )
        conn.commit()
        return False
    return True


def _log_audit(
    conn: sqlite3.Connection,
    ip_hash: str,
    key_prefix: str,
    success: bool,
    reason: Optional[str] = None,
) -> None:
    """Record validation attempt to audit log."""
    conn.execute(
        'INSERT INTO validation_audit '
        '(timestamp, ip_hash, key_prefix, success, reason) '
        'VALUES (?, ?, ?, ?, ?)',
        (time.time(), ip_hash, key_prefix, 1 if success else 0, reason),
    )
    conn.commit()


def validate_license(
    license_key: str,
    ip: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> ValidationResult:
    """Server-side license validation. Call this on EVERY privileged operation.

    Returns ValidationResult with:
    - valid=True + plan + email when license is active
    - valid=False + reason when rejected
    - locked_out=True when IP rate-limited (also valid=False)

    Side effects:
    - Logs attempt to validation_audit table (success and failure both)
    - Updates last_used_at on success
    - Trips rate limit lockout on repeated failures

    Privacy: never logs full license key, only first 12 chars. IP is hashed.
    """
    ip_hash = _hash_ip(ip or '')
    key_prefix_str = _key_prefix(license_key)
    conn = _connect(db_path)
    try:
        # Rate limit check FIRST (deny before doing DB lookup)
        if _is_locked_out(conn, ip_hash):
            _log_audit(conn, ip_hash, key_prefix_str, False, 'IP_LOCKED_OUT')
            return ValidationResult(
                valid=False,
                reason='Rate limit exceeded — try again in 24h',
                locked_out=True,
            )

        # Format validation FIRST (don't even query DB if malformed)
        if not license_key or not LICENSE_KEY_PATTERN.match(license_key):
            _log_audit(conn, ip_hash, key_prefix_str, False, 'BAD_FORMAT')
            _check_rate_limit(conn, ip_hash)
            return ValidationResult(
                valid=False,
                reason='Invalid license format',
            )

        # DB lookup
        row = conn.execute(
            'SELECT email, plan, status FROM licenses WHERE license_key = ?',
            (license_key,),
        ).fetchone()

        if not row:
            _log_audit(conn, ip_hash, key_prefix_str, False, 'NOT_FOUND')
            _check_rate_limit(conn, ip_hash)
            return ValidationResult(
                valid=False,
                reason='License not found',
            )

        email, plan, status = row
        if status != 'active':
            _log_audit(conn, ip_hash, key_prefix_str, False, f'STATUS_{status}')
            _check_rate_limit(conn, ip_hash)
            return ValidationResult(
                valid=False,
                reason=f'License {status}',
                email=email,
                plan=plan,
            )

        # All checks passed — update last_used + log success
        conn.execute(
            'UPDATE licenses SET last_used_at = ? WHERE license_key = ?',
            (time.time(), license_key),
        )
        _log_audit(conn, ip_hash, key_prefix_str, True, None)
        conn.commit()
        return ValidationResult(
            valid=True,
            plan=plan,
            email=email,
        )
    finally:
        conn.close()


def revoke_license(
    license_key: str,
    reason: str = 'revoked',
    db_path: Optional[Path] = None,
) -> bool:
    """Mark license as revoked. Returns True if updated, False if not found."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            'UPDATE licenses SET status = ? WHERE license_key = ?',
            (reason if reason in {'refunded', 'revoked'} else 'revoked',
             license_key),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_recent_failures(
    ip: str,
    window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    db_path: Optional[Path] = None,
) -> int:
    """Read-only: count recent failures for an IP. Useful for monitoring."""
    ip_hash = _hash_ip(ip)
    conn = _connect(db_path)
    try:
        return conn.execute(
            'SELECT COUNT(*) FROM validation_audit '
            'WHERE ip_hash = ? AND success = 0 AND timestamp > ?',
            (ip_hash, time.time() - window_seconds),
        ).fetchone()[0]
    finally:
        conn.close()
