"""Tests for vn_export module — schema stability + non-legal contract."""
import sys
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pytest

from vn_origin_engine import analyze
from vn_suggestions import build_suggestions
from vn_export import (
    build_export_payload,
    EXPORT_SCHEMA_VERSION,
    EXPORT_GENERATOR,
    EXPORT_DISCLAIMER_VN,
    EXPORT_DISCLAIMER_EN,
)


SAMPLE_AI = (
    "Trong thời đại 4.0, chuyển đổi số đã trở nên ngày càng quan trọng "
    "đối với mọi doanh nghiệp. Hôm nay tôi rất hào hứng được chia sẻ "
    "với các bạn một giải pháp toàn diện giúp tối ưu hóa quy trình. "
    "Tuy nhiên, không phải ai cũng hiểu rõ. Do đó, chúng ta cần lưu ý "
    "rằng quy trình này đem lại trải nghiệm tuyệt vời."
)


@pytest.fixture
def payload():
    rep = analyze(SAMPLE_AI, use_llm=False)
    return build_export_payload(rep)


# ---------- Schema shape ----------

def test_schema_version_present_and_current(payload):
    assert payload["schema_version"] == EXPORT_SCHEMA_VERSION


def test_top_level_keys_complete(payload):
    required = {
        "schema_version", "meta", "input", "verdict", "layers",
        "statistical_profile", "llm_rubric", "suggestions",
        "suggestion_summary", "evidence",
    }
    assert required <= set(payload), (
        f"Missing top-level keys: {required - set(payload)}"
    )


def test_meta_has_generator_and_disclaimers(payload):
    m = payload["meta"]
    assert m["generator"] == EXPORT_GENERATOR
    assert m["disclaimer_vn"] == EXPORT_DISCLAIMER_VN
    assert m["disclaimer_en"] == EXPORT_DISCLAIMER_EN
    assert "generated_at" in m and isinstance(m["generated_at"], str)


def test_input_block_shape(payload):
    inp = payload["input"]
    assert isinstance(inp["text_hash_sha256"], str)
    assert len(inp["text_hash_sha256"]) == 64
    assert isinstance(inp["text_length_chars"], int)
    assert inp["text_length_chars"] > 0


def test_verdict_block_shape(payload):
    v = payload["verdict"]
    assert v["label"] in {"human", "mixed", "likely_ai", "very_likely_ai"}
    assert v["confidence"] in {"low", "medium", "high"}
    assert 0 <= v["overall_score_0_100"] <= 100


def test_layers_block_normalized_weights(payload):
    weights = payload["layers"]["weights"]
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Weights don't sum to 1.0: {weights}"


def test_statistical_profile_has_all_metrics(payload):
    p = payload["statistical_profile"]
    required = {
        "char_count", "word_count", "sentence_count", "para_count",
        "burstiness_sigma", "ttr_per_100w", "formal_connector_per_100w",
        "dash_per_1000_chars", "avg_sentence_words",
        "para_length_stdev_chars",
    }
    assert required <= set(p)


# ---------- Non-legal contract ----------

def test_disclaimer_vn_explicitly_states_non_legal():
    """Body of the VN disclaimer must NEGATE legal-evidence framing."""
    body = EXPORT_DISCLAIMER_VN.lower()
    assert "không phải" in body
    assert "pháp lý" in body
    # Must literally say "không phải bằng chứng pháp lý" or equivalent
    assert "không phải bằng chứng" in body


def test_disclaimer_en_explicitly_states_non_legal():
    body = EXPORT_DISCLAIMER_EN.lower()
    assert "not legal evidence" in body or "not legal" in body
    assert "not " in body


def test_payload_outside_disclaimers_has_no_legal_framing(payload):
    """Strip disclaimer fields, then scan rest of payload for legal terms.

    The disclaimers are EXPECTED to contain negated legal terms (that's
    their job). The rest of the payload must be free of legal/forensic
    framing per Reframe-A.
    """
    clone = json.loads(json.dumps(payload))  # deep copy
    clone["meta"].pop("disclaimer_vn", None)
    clone["meta"].pop("disclaimer_en", None)
    blob = json.dumps(clone, ensure_ascii=False).lower()
    forbidden = [
        "công văn 314", "verifier nguồn gốc", "single report",
        "forensic", "authorship attribution",
        "bằng chứng pháp lý", "legal evidence",
    ]
    for term in forbidden:
        assert term not in blob, (
            f"Non-disclaimer payload leaks legal framing: {term!r}"
        )


# ---------- Suggestions integration ----------

def test_suggestions_array_matches_build_suggestions(payload):
    rep = analyze(SAMPLE_AI, use_llm=False)
    expected = build_suggestions(rep)
    assert len(payload["suggestions"]) == len(expected)
    for actual, exp in zip(payload["suggestions"], expected):
        assert actual["flag_id"] == exp.flag_id
        assert actual["rewrite_hint"] == exp.rewrite_hint


def test_suggestion_summary_counts_match(payload):
    sugs = payload["suggestions"]
    summary = payload["suggestion_summary"]
    assert summary["total_suggestions"] == len(sugs)
    by_sev = summary["by_severity"]
    counted = sum(by_sev.values())
    assert counted == len(sugs)


# ---------- Serialization ----------

def test_payload_is_json_serializable(payload):
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    assert len(blob) > 100
    # Roundtrip
    parsed = json.loads(blob)
    assert parsed["schema_version"] == payload["schema_version"]


def test_exclude_raw_evidence_drops_field():
    rep = analyze(SAMPLE_AI, use_llm=False)
    payload = build_export_payload(rep, include_raw_evidence=False)
    assert "evidence" not in payload
    # Suggestions still present (summarized representation)
    assert "suggestions" in payload


def test_unicode_vn_chars_preserved(payload):
    blob = json.dumps(payload, ensure_ascii=False)
    assert "tiếng việt" in blob.lower() or "Tiếng Việt" in blob
    assert "ạ" in blob or "ả" in blob or "ế" in blob or "ổ" in blob
