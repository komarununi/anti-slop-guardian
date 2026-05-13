"""
VN Export — structured JSON payload for Soi Văn Bản results.

Schema versioning lives here, not in the engine, so engine internals can
evolve independently of the public export contract.

Public schema 1.1 (2026-05-13):
  - Bumped from 1.0: adds `suggestions` array + `meta` block
  - Removed: nothing from 1.0 (additive only)
  - Stripped: implementation-detail keys (e.g. `layer_weights` internal name)

NO LEGAL CLAIMS in the payload. Labels are improvement-flavored.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from vn_suggestions import Suggestion, suggestions_to_dicts

EXPORT_SCHEMA_VERSION = "1.1"
EXPORT_GENERATOR = "Komaru Anti-Slop · Tiếng Việt"
EXPORT_DISCLAIMER_VN = (
    "Kết quả phân tích chỉ mang tính tham khảo để cải thiện văn bản. "
    "Không phải bằng chứng pháp lý hoặc kết luận xác thực nguồn gốc. "
    "Văn bản học thuật, bản dịch, hoặc nội dung theo template chặt chẽ "
    "có thể bị nhận nhầm."
)
EXPORT_DISCLAIMER_EN = (
    "Analysis output is an editorial improvement aid only, not legal "
    "evidence or authorship attribution. Academic, translated, or "
    "template-driven text may produce false positives."
)


def build_export_payload(report,
                         suggestions: Optional[List[Suggestion]] = None,
                         include_raw_evidence: bool = True) -> Dict:
    """Assemble the canonical export payload.

    Args:
        report: vn_origin_engine.AuthorshipReport
        suggestions: optional pre-built suggestion list (saves recomputation)
        include_raw_evidence: if False, drop `evidence` array (smaller payload)

    Returns:
        dict ready for json.dumps(..., ensure_ascii=False, indent=2)
    """
    # Lazy import to avoid circular if engine imports this someday
    if suggestions is None:
        from vn_suggestions import build_suggestions
        suggestions = build_suggestions(report)

    payload: Dict = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "meta": {
            "generator": EXPORT_GENERATOR,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "disclaimer_vn": EXPORT_DISCLAIMER_VN,
            "disclaimer_en": EXPORT_DISCLAIMER_EN,
        },
        "input": {
            "text_hash_sha256": report.text_hash,
            "text_length_chars": report.text_length_chars,
            "analyzed_at": report.timestamp_iso,
        },
        "verdict": {
            "label": report.verdict,
            "confidence": report.confidence,
            "overall_score_0_100": report.overall_score,
        },
        "layers": {
            "scores": dict(report.layer_scores),
            "weights": {k: round(v, 4)
                        for k, v in report.layer_weights.items()},
        },
        "statistical_profile": _statistical_to_dict(report.statistical),
        "llm_rubric": _llm_to_dict(report.llm),
        "suggestions": suggestions_to_dicts(suggestions),
        "suggestion_summary": _suggestion_summary(suggestions),
    }

    if include_raw_evidence:
        payload["evidence"] = [_evidence_to_dict(e) for e in report.evidence]

    return payload


def _statistical_to_dict(p) -> Dict:
    return {
        "char_count": p.char_count,
        "word_count": p.word_count,
        "sentence_count": p.sentence_count,
        "para_count": p.para_count,
        "burstiness_sigma": round(p.burstiness, 4),
        "ttr_per_100w": round(p.ttr_per_100w, 4),
        "formal_connector_per_100w": round(p.formal_connector_per_100w, 4),
        "dash_per_1000_chars": round(p.dash_per_1000_chars, 4),
        "avg_sentence_words": round(p.avg_sentence_words, 2),
        "para_length_stdev_chars": round(p.para_length_stdev, 2),
    }


def _llm_to_dict(llm) -> Dict:
    out = {
        "available": llm.available,
        "verdict": llm.verdict,
        "overall_ai_likelihood_0_100": llm.overall_ai_likelihood,
        "scores": dict(llm.scores) if llm.scores else {},
        "evidence": list(llm.evidence) if llm.evidence else [],
        "caveats": list(llm.caveats) if llm.caveats else [],
        "redactions_applied": llm.redactions_applied,
    }
    if llm.error:
        out["unavailable_reason"] = llm.error
    return out


def _evidence_to_dict(ev) -> Dict:
    return {
        "layer": ev.layer,
        "rule": ev.rule,
        "severity": ev.severity,
        "snippet": ev.snippet,
        "explanation": ev.explanation,
    }


def _suggestion_summary(suggestions: List[Suggestion]) -> Dict:
    sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    cat: Dict[str, int] = {}
    total_hits = 0
    for s in suggestions:
        sev[s.severity] = sev.get(s.severity, 0) + 1
        cat[s.category] = cat.get(s.category, 0) + 1
        total_hits += s.hit_count
    return {
        "total_suggestions": len(suggestions),
        "total_flag_hits": total_hits,
        "by_severity": sev,
        "by_category": cat,
    }


# ============================================================
# CLI smoke
# ============================================================

if __name__ == "__main__":
    import sys
    import json
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from vn_origin_engine import analyze
    from vn_suggestions import build_suggestions

    sample = (
        "Trong thời đại 4.0, chuyển đổi số đã trở nên ngày càng quan trọng "
        "đối với mọi doanh nghiệp. Hôm nay tôi rất hào hứng được chia sẻ "
        "với các bạn một giải pháp toàn diện."
    )
    rep = analyze(sample, use_llm=False)
    sugs = build_suggestions(rep)
    payload = build_export_payload(rep, sugs)
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])
