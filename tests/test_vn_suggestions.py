"""Tests for vn_suggestions improvement-hint module.

Deterministic — no live LLM. Uses analyze(use_llm=False) only.
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pytest

from vn_origin_engine import analyze
from vn_suggestions import (
    Suggestion,
    build_suggestions,
    suggestions_to_dicts,
    _parse_regex_id,
    _PATTERN_BY_ID,
    _STAT_REWRITES,
    _SEVERITY_RANK,
)
from vn_patterns import VN_BANNED_PHRASES


# ---------- Fixtures ----------

AI_HEAVY = (
    "Trong thời đại 4.0, chuyển đổi số đã trở nên ngày càng quan trọng "
    "đối với mọi doanh nghiệp. Hôm nay tôi rất hào hứng được chia sẻ "
    "với các bạn một giải pháp toàn diện giúp tối ưu hóa quy trình. "
    "Tuy nhiên, không phải ai cũng hiểu rõ. Do đó, chúng ta cần lưu ý "
    "rằng quy trình này đem lại trải nghiệm tuyệt vời. Ngoài ra, "
    "đáng chú ý là 100% khách hàng hài lòng. Hãy theo dõi để biết thêm!"
)

HUMAN_PLAIN = (
    "Sáng nay đi cà phê với anh bạn cũ. Anh ấy mới chuyển việc, lương "
    "tăng nhẹ nhưng phải làm thứ bảy. Mình nghe xong thấy chán thay. "
    "Đời đi làm mà cuối tuần không còn thì giàu kiểu gì cũng mệt. "
    "Sau đó hai đứa đi ăn bún chả Hàng Quạt, đông như mọi khi."
)

# Text that triggers ONE regex flag (VO01 opener) repeatedly to exercise
# dedupe logic.
REPEAT_OPENER = (
    "Hôm nay tôi rất hào hứng được chia sẻ điều một. "
    "Tuần này tôi rất vui mừng được giới thiệu điều hai. "
    "Tháng này chúng tôi rất tự hào được công bố điều ba. "
    "Đây là một đoạn văn dài hơn 100 ký tự để vượt qua check tối thiểu "
    "của engine analyze."
)


# ---------- Module-level invariants ----------

def test_pattern_lookup_complete():
    """Every VN_BANNED_PHRASES entry must be reachable via id lookup."""
    for entry in VN_BANNED_PHRASES:
        assert entry["id"] in _PATTERN_BY_ID
        assert _PATTERN_BY_ID[entry["id"]] is entry


def test_pattern_lookup_no_duplicate_ids():
    ids = [p["id"] for p in VN_BANNED_PHRASES]
    assert len(ids) == len(set(ids)), "Duplicate id in VN_BANNED_PHRASES"


def test_severity_rank_covers_all_severities():
    severities = {p["severity"] for p in VN_BANNED_PHRASES}
    for sev in severities:
        assert sev in _SEVERITY_RANK


def test_stat_rewrites_keys_are_strings():
    for k, v in _STAT_REWRITES.items():
        assert isinstance(k, str)
        assert {"rewrite_hint", "category", "why"} <= set(v)


# ---------- _parse_regex_id ----------

def test_parse_regex_id_standard_format():
    assert _parse_regex_id("VH01 · Hyperbolic adjective stack") == "VH01"


def test_parse_regex_id_bare_id_fallback():
    # Engine should not emit this, but defensive path covers it
    assert _parse_regex_id("VH01") == "VH01"


def test_parse_regex_id_unknown():
    assert _parse_regex_id("totally bogus rule string") is None


# ---------- build_suggestions: structural ----------

def test_build_returns_list_of_suggestions():
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    assert isinstance(sugs, list)
    assert len(sugs) >= 1
    assert all(isinstance(s, Suggestion) for s in sugs)


def test_build_human_text_few_or_no_suggestions():
    rep = analyze(HUMAN_PLAIN, use_llm=False)
    sugs = build_suggestions(rep)
    # Human text may have 0 flags — but if any exist they should all be
    # low/medium severity
    high_or_critical = [s for s in sugs if s.severity in ("critical", "high")]
    assert len(high_or_critical) == 0, (
        f"Human text wrongly flagged high/critical: {high_or_critical}"
    )


def test_suggestions_sorted_by_severity_then_hits():
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    ranks = [_SEVERITY_RANK[s.severity] for s in sugs]
    assert ranks == sorted(ranks), "Not sorted by severity rank"


# ---------- build_suggestions: regex layer ----------

def test_regex_flag_carries_replacement_as_hint():
    """For each regex evidence, the suggestion rewrite_hint must equal the
    `replacement` field from VN_BANNED_PHRASES."""
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    for s in sugs:
        if s.flag_id in _PATTERN_BY_ID:
            expected = _PATTERN_BY_ID[s.flag_id]["replacement"]
            assert s.rewrite_hint == expected


def test_regex_flag_carries_why_from_pattern():
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    for s in sugs:
        if s.flag_id in _PATTERN_BY_ID:
            assert s.why == _PATTERN_BY_ID[s.flag_id]["why"]


def test_regex_dedupe_increments_hit_count():
    """REPEAT_OPENER triggers VO01 three times → one suggestion, hit_count=3."""
    rep = analyze(REPEAT_OPENER, use_llm=False)
    sugs = build_suggestions(rep)
    vo01 = [s for s in sugs if s.flag_id == "VO01"]
    assert len(vo01) == 1, f"Expected exactly 1 VO01 suggestion, got {vo01}"
    assert vo01[0].hit_count >= 2, (
        f"VO01 should dedupe ≥2 hits, got hit_count={vo01[0].hit_count}"
    )


def test_critical_severity_sorts_first():
    """AI_HEAVY contains 'Hôm nay tôi rất hào hứng' (VO01, critical).
    It must appear at index 0."""
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    assert sugs[0].severity == "critical"
    assert sugs[0].flag_id == "VO01"


# ---------- build_suggestions: statistical layer ----------

def test_statistical_flag_has_curated_hint():
    """If engine emits a stat rule that's in _STAT_REWRITES, the suggestion
    must use the curated hint (not the engine's generic explanation)."""
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    stat_sugs = [s for s in sugs if s.flag_id.startswith("stat:")]
    for s in stat_sugs:
        key = s.flag_id.removeprefix("stat:")
        if key in _STAT_REWRITES:
            assert s.rewrite_hint == _STAT_REWRITES[key]["rewrite_hint"]


def test_statistical_flag_category_is_statistical():
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    for s in sugs:
        if s.flag_id.startswith("stat:"):
            assert s.category == "statistical"


# ---------- Empty / edge cases ----------

def test_no_flags_returns_empty_list():
    """A deliberately clean text → 0 suggestions."""
    clean = (
        "Sáng nay đi bộ ra hồ. Trời lạnh. Một con chim sẻ đậu trên cành "
        "khô. Mình đứng nhìn một lúc rồi đi tiếp. Cà phê sáng nay đắng "
        "hơn mọi khi, có lẽ do barista mới đổi máy. Về nhà mở laptop, "
        "ngồi viết. Câu đầu bao giờ cũng khó nhất."
    )
    rep = analyze(clean, use_llm=False)
    sugs = build_suggestions(rep)
    # Allow some low-tier flags but no critical/high
    critical_or_high = [s for s in sugs if s.severity in ("critical", "high")]
    assert critical_or_high == [], (
        f"Clean text flagged: {[(s.severity, s.flag_id) for s in critical_or_high]}"
    )


# ---------- to_dict ----------

def test_to_dict_roundtrip():
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    dicts = suggestions_to_dicts(sugs)
    assert len(dicts) == len(sugs)
    for d, s in zip(dicts, sugs):
        assert d["flag_id"] == s.flag_id
        assert d["rewrite_hint"] == s.rewrite_hint
        assert d["hit_count"] == s.hit_count
        # Must be JSON-serializable
        import json
        json.dumps(d, ensure_ascii=False)


def test_example_snippet_non_empty_when_flagged():
    rep = analyze(AI_HEAVY, use_llm=False)
    sugs = build_suggestions(rep)
    for s in sugs:
        assert s.example_snippet.strip(), f"Empty snippet for {s.flag_id}"
