"""Tests for the Pro waitlist lead capture module."""
import csv
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pytest

import lead_capture as lc


@pytest.fixture
def temp_csv(tmp_path, monkeypatch):
    """Redirect LEADS_CSV to a tmp file for isolation."""
    target = tmp_path / "pro_leads.csv"
    monkeypatch.setattr(lc, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lc, "LEADS_CSV", target)
    return target


# ---------- Email validation ----------

@pytest.mark.parametrize("email,valid", [
    ("user@example.com", True),
    ("user.name+tag@sub.domain.co.uk", True),
    ("a@b.co", True),
    ("not-an-email", False),
    ("@example.com", False),
    ("user@", False),
    ("user@.com", False),
    ("", False),
    ("   ", False),
    ("a" * 250 + "@example.com", False),  # too long
])
def test_is_valid_email(email, valid):
    assert lc.is_valid_email(email) is valid


# ---------- Capture ----------

def test_capture_new_lead(temp_csv):
    r = lc.capture_lead("user@example.com", tier="Pro Monthly")
    assert r.ok
    assert not r.duplicate
    assert "Cảm ơn" in r.message
    assert temp_csv.exists()
    with temp_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["email"] == "user@example.com"
    assert rows[0]["tier"] == "Pro Monthly"


def test_capture_email_normalization(temp_csv):
    r = lc.capture_lead("  USER@Example.COM  ", tier="Pro Monthly")
    assert r.ok
    with temp_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["email"] == "user@example.com"


def test_capture_duplicate_detected(temp_csv):
    lc.capture_lead("user@example.com")
    r2 = lc.capture_lead("user@example.com")
    assert r2.ok
    assert r2.duplicate
    assert "đã được ghi nhận" in r2.message
    with temp_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1, "duplicate should not append a second row"


def test_capture_duplicate_case_insensitive(temp_csv):
    lc.capture_lead("user@example.com")
    r2 = lc.capture_lead("USER@EXAMPLE.COM")
    assert r2.duplicate


def test_capture_invalid_email(temp_csv):
    r = lc.capture_lead("not-email")
    assert not r.ok
    assert "không hợp lệ" in r.message
    assert not temp_csv.exists()


def test_capture_writes_header_on_first_write(temp_csv):
    lc.capture_lead("first@example.com")
    with temp_csv.open(encoding="utf-8") as f:
        first_line = f.readline().strip()
    assert "timestamp" in first_line
    assert "email" in first_line
    assert "tier" in first_line


def test_capture_ua_hash_truncated(temp_csv):
    lc.capture_lead("user@example.com", user_agent="Mozilla/5.0 ...")
    with temp_csv.open(encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert len(row["ua_hash"]) == 16


def test_capture_ua_empty_when_not_provided(temp_csv):
    lc.capture_lead("user@example.com")
    with temp_csv.open(encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["ua_hash"] == ""


def test_lead_count(temp_csv):
    assert lc.lead_count() == 0
    lc.capture_lead("a@example.com")
    lc.capture_lead("b@example.com")
    lc.capture_lead("a@example.com")  # duplicate
    assert lc.lead_count() == 2


def test_telegram_notify_silent_without_env(temp_csv, monkeypatch):
    """Should not raise even if TELEGRAM env vars missing."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    r = lc.capture_lead("user@example.com", notify_telegram=True)
    assert r.ok  # silent fallback
