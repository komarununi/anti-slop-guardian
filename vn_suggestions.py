"""
VN Suggestions — Improvement Hints per Flag
============================================

Takes an AuthorshipReport from vn_origin_engine and produces deduplicated,
priority-sorted rewrite hints per flag.

Design:
  - Regex flags: look up `replacement` field from VN_BANNED_PHRASES by id
  - Statistical flags: curated rewrite advice keyed by rule name
  - LLM evidence: passthrough as info-tier suggestion
  - Dedupe by flag_id (3 hits of VH01 collapse to 1 suggestion with hit_count)
  - Sort: severity (critical > high > medium > low > info), then hit_count desc

NO LLM in this module. Pure deterministic transformation.

Schema (Suggestion):
  flag_id          str   stable id (e.g. "VH01", "stat:burstiness_strong",
                                       "llm:evidence_3")
  category         str   "hyperbole" | "translationese" | "filler" | "cta"
                          | "opener" | "structure" | "statistical" | "llm"
  rule             str   short label
  severity         str   critical | high | medium | low | info
  hit_count        int   how many times this flag triggered
  example_snippet  str   one example from the text (first hit)
  rewrite_hint     str   actionable VN rewrite advice
  why              str   1-line rationale (VN)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from vn_patterns import VN_BANNED_PHRASES


# Build id → entry lookup once at import time
_PATTERN_BY_ID: Dict[str, dict] = {p["id"]: p for p in VN_BANNED_PHRASES}


# Statistical rule → (rewrite_hint, why) — keyed by exact rule string emitted
# by vn_origin_engine._score_statistical
_STAT_REWRITES: Dict[str, Dict[str, str]] = {
    "Độ dài câu quá đồng đều": {
        "rewrite_hint": (
            "Xen kẽ một số câu ngắn (5-10 từ) giữa các câu dài. "
            "Bắt đầu một đoạn bằng câu cụt cũng được."
        ),
        "category": "statistical",
        "why": "Văn bản người viết tự nhiên có nhịp lên-xuống về độ dài câu.",
    },
    "Độ dài câu khá đồng đều": {
        "rewrite_hint": (
            "Cắt 1-2 câu dài thành 2 câu ngắn để tạo nhịp."
        ),
        "category": "statistical",
        "why": "Nhịp câu đều quá tạo cảm giác máy đọc.",
    },
    "Vốn từ lặp lại": {
        "rewrite_hint": (
            "Tìm 3-5 từ lặp lại nhiều nhất và thay bằng đồng nghĩa cụ thể "
            "(không phải từ chung chung như 'điều này', 'việc đó')."
        ),
        "category": "statistical",
        "why": "AI hay xoay vòng một bộ từ vựng hẹp.",
    },
    "Liên từ trang trọng tần suất cao": {
        "rewrite_hint": (
            "Cắt phần lớn 'tuy nhiên', 'do đó', 'ngoài ra', 'bên cạnh đó'. "
            "Người viết thật để câu nối với nhau bằng nội dung, không bằng "
            "liên từ template."
        ),
        "category": "statistical",
        "why": "Liên từ formal lạm dụng là dấu hiệu rõ nhất của VN AI text.",
    },
    "Em-dash tần suất cao": {
        "rewrite_hint": (
            "Thay phần lớn em-dash (—) bằng dấu phẩy, dấu chấm, hoặc tách "
            "thành câu mới. Tiếng Việt ít khi dùng em-dash đặc."
        ),
        "category": "statistical",
        "why": "Em-dash đặc là dấu vân tay của bản dịch máy từ tiếng Anh.",
    },
    "Độ dài câu trung bình thuộc dải AI": {
        "rewrite_hint": (
            "Cắt vài câu dài xuống dưới 18 từ. Mục tiêu: vài câu rất "
            "ngắn (5-10 từ), vài câu trung bình, ít câu dài."
        ),
        "category": "statistical",
        "why": "Trung bình 24-32 từ/câu là dải AI thường xuyên đẻ ra.",
    },
    "Độ dài đoạn đồng đều": {
        "rewrite_hint": (
            "Làm cho các đoạn khác nhau rõ rệt: một đoạn dài kể ví dụ, "
            "một đoạn 2-3 dòng kết luận, một đoạn 1 câu chuyển ý."
        ),
        "category": "statistical",
        "why": "Đoạn đều răm rắp = cấu trúc theo outline cứng.",
    },
}


_SEVERITY_RANK = {
    "critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4,
}


@dataclass
class Suggestion:
    flag_id: str
    category: str
    rule: str
    severity: str
    hit_count: int
    example_snippet: str
    rewrite_hint: str
    why: str

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_regex_id(rule_field: str) -> Optional[str]:
    """Engine writes rule = f'{id} · {label}'. Extract id."""
    if " · " in rule_field:
        return rule_field.split(" · ", 1)[0].strip()
    # Fallback: rule_field might already be a bare id (defensive)
    if rule_field in _PATTERN_BY_ID:
        return rule_field
    return None


def build_suggestions(report) -> List[Suggestion]:
    """Build deduplicated, priority-sorted suggestions from an AuthorshipReport.

    Args:
        report: vn_origin_engine.AuthorshipReport instance.

    Returns:
        List[Suggestion] sorted by (severity_rank, -hit_count).
    """
    # Bucket by stable flag_id
    buckets: Dict[str, Suggestion] = {}

    for ev in report.evidence:
        if ev.layer == "regex":
            pat_id = _parse_regex_id(ev.rule)
            if pat_id is None or pat_id not in _PATTERN_BY_ID:
                continue
            entry = _PATTERN_BY_ID[pat_id]
            existing = buckets.get(pat_id)
            if existing is None:
                buckets[pat_id] = Suggestion(
                    flag_id=pat_id,
                    category=entry["category"],
                    rule=entry["rule"],
                    severity=entry["severity"],
                    hit_count=1,
                    example_snippet=ev.snippet,
                    rewrite_hint=entry["replacement"],
                    why=entry["why"],
                )
            else:
                existing.hit_count += 1

        elif ev.layer == "statistical":
            # Use exact rule string as id (engine emits stable strings)
            stat_key = ev.rule
            stat_meta = _STAT_REWRITES.get(stat_key)
            if stat_meta is None:
                # Unknown statistical rule — passthrough with generic hint
                stat_meta = {
                    "rewrite_hint": ev.explanation,
                    "category": "statistical",
                    "why": ev.explanation,
                }
            flag_id = f"stat:{stat_key}"
            existing = buckets.get(flag_id)
            if existing is None:
                buckets[flag_id] = Suggestion(
                    flag_id=flag_id,
                    category=stat_meta["category"],
                    rule=stat_key,
                    severity=ev.severity,
                    hit_count=1,
                    example_snippet=ev.snippet,
                    rewrite_hint=stat_meta["rewrite_hint"],
                    why=stat_meta["why"],
                )
            else:
                existing.hit_count += 1

        elif ev.layer == "llm":
            # LLM evidence: each item from claude is a freeform string in
            # ev.snippet. Treat as individual suggestion.
            flag_id = f"llm:{len([k for k in buckets if k.startswith('llm:')])}"
            buckets[flag_id] = Suggestion(
                flag_id=flag_id,
                category="llm",
                rule="Claude rubric",
                severity=ev.severity or "info",
                hit_count=1,
                example_snippet=ev.snippet,
                rewrite_hint=ev.snippet,
                why="Quan sát từ Claude rubric.",
            )

    suggestions = list(buckets.values())
    suggestions.sort(
        key=lambda s: (_SEVERITY_RANK.get(s.severity, 99), -s.hit_count)
    )
    return suggestions


def suggestions_to_dicts(suggestions: List[Suggestion]) -> List[dict]:
    return [s.to_dict() for s in suggestions]


# ============================================================
# CLI smoke
# ============================================================

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from vn_origin_engine import analyze

    sample = (
        "Trong thời đại 4.0, chuyển đổi số đã trở nên ngày càng quan trọng "
        "đối với mọi doanh nghiệp. Hôm nay tôi rất hào hứng được chia sẻ "
        "với các bạn một giải pháp toàn diện giúp tối ưu hóa quy trình. "
        "Tuy nhiên, không phải ai cũng hiểu rõ. Do đó, chúng ta cần lưu ý "
        "rằng quy trình này đem lại trải nghiệm tuyệt vời. Ngoài ra, "
        "đáng chú ý là 100% khách hàng hài lòng. Hãy theo dõi để biết thêm!"
    )
    rep = analyze(sample, use_llm=False)
    sugs = build_suggestions(rep)
    print(f"Total suggestions: {len(sugs)}\n")
    for s in sugs[:10]:
        print(f"[{s.severity}] {s.flag_id} ({s.hit_count}×) — {s.rule}")
        print(f"  hint: {s.rewrite_hint}")
        print(f"  why:  {s.why}\n")
