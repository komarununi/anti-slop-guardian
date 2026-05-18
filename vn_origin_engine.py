"""
VN Origin Verifier — Hybrid Engine
====================================

3 layers:
  1. **Regex** — VN_BANNED_PHRASES from vn_patterns.py (transparent + cheap)
  2. **Statistical features** — burstiness, TTR, dash density, connector freq
                                (transparent + cheap, language-aware tuned for VN)
  3. **LLM rubric** — Claude API call via safe_llm_send (TIER 0 privacy gate),
                      OPTIONAL: skip if no API key → fall back to layer 1+2

Output: AuthorshipReport with weighted score + per-layer evidence + reproducible
hash (text → SHA-256). PDF report renderer in `report_generator.py`.

Privacy: every text goes through scrub before LLM call (TIER 0 contract).
Engine NEVER stores user text — only hash + score in DB if persistence enabled.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from vn_patterns import (
    VN_BANNED_PHRASES,
    VN_STATISTICAL_THRESHOLDS,
    VN_AI_CONNECTORS,
    VN_LLM_RUBRIC_PROMPT,
)

logger = logging.getLogger(__name__)


# ============================================================
# Result dataclasses
# ============================================================

@dataclass
class LayerEvidence:
    """One concrete signal found by a layer."""
    layer: str               # "regex" | "statistical" | "llm"
    rule: str
    severity: str            # "critical" | "high" | "medium" | "low" | "info"
    snippet: str             # quoted text or numeric finding
    explanation: str         # 1-line VN reason


@dataclass
class StatisticalProfile:
    """All numeric features of the text."""
    char_count: int
    word_count: int
    sentence_count: int
    para_count: int
    burstiness: float                # stdev of sentence lengths
    ttr_per_100w: float              # type-token ratio
    formal_connector_per_100w: float
    dash_per_1000_chars: float
    avg_sentence_words: float
    para_length_stdev: float


@dataclass
class LLMRubric:
    """Optional LLM scoring layer result."""
    available: bool
    overall_ai_likelihood: int = 0
    verdict: str = "skipped"
    scores: Dict[str, int] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    redactions_applied: int = 0
    error: Optional[str] = None


@dataclass
class AuthorshipReport:
    """Final aggregated report."""
    text_hash: str               # SHA-256 of input (reproducibility)
    text_length_chars: int
    timestamp_iso: str
    overall_score: int           # 0-100, higher = more AI-like
    verdict: str                 # "human" | "mixed" | "likely_ai" | "very_likely_ai"
    confidence: str              # "low" | "medium" | "high"
    statistical: StatisticalProfile
    llm: LLMRubric
    evidence: List[LayerEvidence]
    layer_scores: Dict[str, int]  # per-layer 0-100
    layer_weights: Dict[str, float]
    schema_version: str = "1.0"
    override_reason: Optional[str] = None  # set when F1 verdict-override fires

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


# ============================================================
# Layer 1: Regex (VN banned phrases)
# ============================================================

def _scan_regex(text: str) -> Tuple[int, List[LayerEvidence]]:
    """Return (score 0-100, evidence list). Score = severity-weighted hit count."""
    evidence: List[LayerEvidence] = []
    weight_map = {"critical": 25, "high": 12, "medium": 6, "low": 2}
    raw = 0
    for p in VN_BANNED_PHRASES:
        compiled = re.compile(p["pattern"], re.IGNORECASE)
        for m in compiled.finditer(text):
            snippet = _ctx(text, m.start(), m.end(), 40)
            evidence.append(LayerEvidence(
                layer="regex",
                rule=p["id"] + " · " + p["rule"],
                severity=p["severity"],
                snippet=snippet,
                explanation=p["why"],
            ))
            raw += weight_map.get(p["severity"], 1)
    # Normalize per 1000 chars so length doesn't bias
    per_1000 = (raw / max(len(text), 1)) * 1000
    score = min(100, int(per_1000 * 2))  # tuneable cap
    return score, evidence


def _ctx(text: str, start: int, end: int, ctx: int = 40) -> str:
    s = max(0, start - ctx)
    e = min(len(text), end + ctx)
    prefix = "…" if s > 0 else ""
    suffix = "…" if e < len(text) else ""
    return f"{prefix}{text[s:e]}{suffix}"


# ============================================================
# Layer 2: Statistical features
# ============================================================

def _statistical_profile(text: str) -> StatisticalProfile:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    words = text.split()
    word_count = len(words)
    sent_lengths = [len(s.split()) for s in sentences] or [0]

    burstiness = statistics.stdev(sent_lengths) if len(sent_lengths) > 1 else 0.0
    avg_sent = statistics.mean(sent_lengths) if sent_lengths else 0.0

    # TTR per 100w (avg across windows)
    ttrs = []
    for i in range(0, max(1, word_count - 99), 100):
        chunk = words[i:i + 100]
        if len(chunk) < 50:
            continue
        ttrs.append(len(set(w.lower() for w in chunk)) / len(chunk))
    ttr = statistics.mean(ttrs) if ttrs else (
        len(set(w.lower() for w in words)) / max(word_count, 1)
    )

    # Formal-connector freq
    text_lower = text.lower()
    conn_hits = sum(text_lower.count(c) for c in VN_AI_CONNECTORS)
    conn_per_100w = (conn_hits / max(word_count, 1)) * 100

    # Dash density per 1000 chars
    dash_count = text.count("—") + text.count("–")
    dash_per_1000 = (dash_count / max(len(text), 1)) * 1000

    # Para length stdev
    para_chars = [len(p) for p in paras] or [0]
    para_stdev = statistics.stdev(para_chars) if len(para_chars) > 1 else 0.0

    return StatisticalProfile(
        char_count=len(text),
        word_count=word_count,
        sentence_count=len(sentences),
        para_count=len(paras),
        burstiness=burstiness,
        ttr_per_100w=ttr,
        formal_connector_per_100w=conn_per_100w,
        dash_per_1000_chars=dash_per_1000,
        avg_sentence_words=avg_sent,
        para_length_stdev=para_stdev,
    )


def _score_statistical(p: StatisticalProfile) -> Tuple[int, List[LayerEvidence]]:
    th = VN_STATISTICAL_THRESHOLDS
    evidence: List[LayerEvidence] = []
    score = 0  # higher = more AI-like

    # Burstiness too low → AI
    if p.burstiness < th["burstiness_strong_ai"]:
        score += 30
        evidence.append(LayerEvidence(
            layer="statistical", rule="Độ dài câu quá đồng đều", severity="high",
            snippet=f"Độ lệch chuẩn σ={p.burstiness:.2f} (ngưỡng {th['burstiness_strong_ai']})",
            explanation=("Các câu có độ dài gần tương đương. Văn bản tự nhiên "
                         "thường có sự xen kẽ giữa câu ngắn và câu dài."),
        ))
    elif p.burstiness < th["burstiness_min_human"]:
        score += 15
        evidence.append(LayerEvidence(
            layer="statistical", rule="Độ dài câu khá đồng đều", severity="medium",
            snippet=f"Độ lệch chuẩn σ={p.burstiness:.2f}",
            explanation="Có thể bổ sung một vài câu ngắn để tăng nhịp điệu.",
        ))

    # TTR too low → AI repetitive
    if p.ttr_per_100w < th["ttr_min_human_per_100w"]:
        score += 20
        evidence.append(LayerEvidence(
            layer="statistical", rule="Vốn từ lặp lại", severity="medium",
            snippet=f"Tỉ lệ từ khác biệt = {p.ttr_per_100w:.2f}",
            explanation=("Một số từ được lặp lại trong khoảng cách ngắn. "
                         "Đây là đặc trưng thường gặp ở văn bản AI."),
        ))

    # Formal connectors over-used
    if p.formal_connector_per_100w > th["formal_connector_max_per_100w"]:
        score += 25
        evidence.append(LayerEvidence(
            layer="statistical", rule="Liên từ trang trọng tần suất cao",
            severity="high",
            snippet=f"{p.formal_connector_per_100w:.1f} liên từ / 100 từ",
            explanation=("Tần suất 'tuy nhiên', 'do đó', 'ngoài ra' cao hơn "
                         "mức thông thường của văn bản tiếng Việt do người viết."),
        ))

    # Dash density too high in VN context
    if p.dash_per_1000_chars > th["dash_per_1000_max_human"]:
        score += 15
        evidence.append(LayerEvidence(
            layer="statistical", rule="Em-dash tần suất cao", severity="medium",
            snippet=f"{p.dash_per_1000_chars:.1f} em-dash / 1000 ký tự",
            explanation=("Văn bản tiếng Việt ít khi sử dụng em-dash với "
                         "tần suất này. Có thể là bản dịch từ tiếng Anh."),
        ))

    # Avg sentence words in AI band
    lo, hi = th["sentence_avg_words_ai_band"]
    if lo <= p.avg_sentence_words <= hi:
        score += 10
        evidence.append(LayerEvidence(
            layer="statistical", rule="Độ dài câu trung bình thuộc dải AI",
            severity="low",
            snippet=f"Trung bình {p.avg_sentence_words:.1f} từ / câu",
            explanation=f"Độ dài câu nằm trong khoảng {lo} đến {hi} từ, "
                        "tương ứng với dải mà AI thường tạo ra.",
        ))

    # Para uniformity
    if p.para_count >= 3 and p.para_length_stdev < th["para_length_stdev_min_human"]:
        score += 10
        evidence.append(LayerEvidence(
            layer="statistical", rule="Độ dài đoạn đồng đều", severity="low",
            snippet=f"Độ lệch chuẩn σ={p.para_length_stdev:.0f} ký tự",
            explanation=("Các đoạn có độ dài tương đương nhau, gợi ý cấu "
                         "trúc theo outline cứng hơn là viết tự nhiên."),
        ))

    return min(100, score), evidence


# ============================================================
# Layer 3: LLM rubric (optional, via safe_llm_send if available)
# ============================================================

# Max chars to send to LLM (matches previous text[:6000] cap)
LLM_INPUT_MAX_CHARS = 6000

# Closing delimiter tag — strip from user input to prevent context escape
_DELIMITER_ESCAPE_PATTERN = re.compile(
    r"</?\s*text_to_analyze\s*/?>", re.IGNORECASE
)

# Control chars except \t \n \r — strip from user input
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_user_text(text: str) -> str:
    """Defense-in-depth: pre-sanitize user input before LLM send.

    1. Cap length to LLM_INPUT_MAX_CHARS (cost control + DoS protection)
    2. Strip control chars (avoid encoding tricks / output corruption)
    3. Strip closing delimiter tags `</text_to_analyze>` (prevent context
       escape — attacker can't close our delimiter early to inject instructions
       in the "outer" space)

    Does NOT touch normal punctuation or Vietnamese diacritics. Privacy gateway
    (safe_llm_send) handles PII scrub downstream — this is just structural
    input hygiene.

    AppSec fix 2026-05-19 (CWE-77 / OWASP A03 Injection).
    """
    if not text:
        return ""
    # 1. Cap length
    sanitized = text[:LLM_INPUT_MAX_CHARS]
    # 2. Strip control chars
    sanitized = _CONTROL_CHARS_PATTERN.sub("", sanitized)
    # 3. Strip delimiter tags (case-insensitive)
    sanitized = _DELIMITER_ESCAPE_PATTERN.sub("", sanitized)
    return sanitized


def _llm_rubric(text: str) -> LLMRubric:
    """Call Claude via safe_llm_send. Returns LLMRubric (available=False on
    any failure — fail-safe so engine still produces score)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return LLMRubric(available=False, error="ANTHROPIC_API_KEY missing")

    try:
        import anthropic  # type: ignore
    except ImportError:
        return LLMRubric(available=False, error="anthropic SDK not installed")

    # Try to use the privacy gateway; fall back to plain call if not available
    # (in deployed komaru-marketing repo, safe_llm_send may not be present —
    # caller can vendor it from external-auditor as needed).
    safe_send = None
    try:
        from privacy_gateway import safe_llm_send  # vendored copy
        safe_send = safe_llm_send
    except ImportError:
        try:
            # Try external-auditor path if mounted alongside
            import sys
            sys.path.insert(0, str(__import__("pathlib").Path(
                __file__).resolve().parents[3] / "external-auditor"))
            from src.privacy import safe_llm_send  # type: ignore
            safe_send = safe_llm_send
        except Exception as e:
            logger.warning("Privacy gateway not loadable (%s) — REFUSING LLM call", e)
            return LLMRubric(available=False,
                             error=f"privacy gateway unavailable: {e}")

    # AppSec fix 2026-05-19: split system instructions from user text to prevent
    # prompt injection. User text goes ONLY in user role wrapped in defensive
    # delimiter; defensive system prompt instructs Claude to ignore injection.
    from vn_patterns import VN_LLM_SYSTEM_PROMPT, VN_LLM_USER_TEMPLATE
    # Pre-sanitize user text: cap length + strip control chars (defense-in-depth
    # before privacy gateway scrub).
    safe_user_text = _sanitize_user_text(text)
    user_message = VN_LLM_USER_TEMPLATE.replace("{text}", safe_user_text)
    client = anthropic.Anthropic(api_key=api_key)

    def _send(scrubbed: str):
        return client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=VN_LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": scrubbed}],
        )

    try:
        gw = safe_send(user_message, _send, fail_closed=True)
    except Exception as e:
        return LLMRubric(available=False, error=f"LLM call failed: {e}")

    try:
        body = "".join(b.text for b in gw.response.content if hasattr(b, "text"))
        # Strip markdown fences if Claude wrapped JSON
        body = body.strip()
        if body.startswith("```"):
            body = re.sub(r"^```(?:json)?\s*", "", body)
            body = re.sub(r"\s*```$", "", body)
        data = json.loads(body)
        return LLMRubric(
            available=True,
            overall_ai_likelihood=int(data.get("overall_ai_likelihood", 0)),
            verdict=data.get("verdict", "mixed"),
            scores=data.get("scores", {}),
            evidence=list(data.get("evidence", []))[:8],
            caveats=list(data.get("caveats", []))[:3],
            redactions_applied=gw.redactions,
        )
    except Exception as e:
        return LLMRubric(available=False, error=f"parse failed: {e}")


# ============================================================
# Aggregator + verdict
# ============================================================

def _verdict(score: int) -> Tuple[str, str]:
    """Map 0-100 → (verdict, confidence)."""
    if score < 25:
        return "human", "medium"
    if score < 50:
        return "mixed", "medium"
    if score < 75:
        return "likely_ai", "medium"
    return "very_likely_ai", "high"


# Verdict tier order — higher index = stronger AI signal
_VERDICT_TIERS = ["human", "mixed", "likely_ai", "very_likely_ai"]


def _apply_regex_override(
    base_verdict: str,
    base_confidence: str,
    regex_evidence: list,
) -> Tuple[str, str, Optional[str]]:
    """Override verdict tier when stacked critical/high regex flags are
    present but weighted score under-counts them.

    Rule (F1 fix 2026-05-13 per validation finding F1):
      - ≥1 critical regex flag  → bump verdict up by 1 tier (min "likely_ai")
      - ≥3 high regex flags     → bump verdict up by 1 tier (min "likely_ai")
      - both conditions         → bump verdict up by 2 tiers (min "likely_ai")

    Rationale: 100% regex score combined with statistical=0 (typical of
    short marketing copy) weighted-averages to 40 → "mixed", which
    under-represents obvious stacked AI signatures. Override raises the
    verdict tier deterministically.

    Returns:
        (new_verdict, new_confidence, override_reason)
        override_reason is None when no override was applied.
    """
    critical_hits = sum(1 for e in regex_evidence
                        if e.layer == "regex" and e.severity == "critical")
    high_hits = sum(1 for e in regex_evidence
                    if e.layer == "regex" and e.severity == "high")

    bumps = 0
    reasons = []
    if critical_hits >= 1:
        bumps += 1
        reasons.append(f"{critical_hits} critical regex flag(s)")
    if high_hits >= 3:
        bumps += 1
        reasons.append(f"{high_hits} high regex flag(s)")

    if bumps == 0:
        return base_verdict, base_confidence, None

    cur_idx = _VERDICT_TIERS.index(base_verdict)
    new_idx = min(len(_VERDICT_TIERS) - 1, cur_idx + bumps)
    # Floor at "likely_ai" when override triggers — critical/high stacking
    # should never leave us at "human" even if base was "human"
    floor_idx = _VERDICT_TIERS.index("likely_ai")
    new_idx = max(new_idx, floor_idx)

    if new_idx == cur_idx:
        return base_verdict, base_confidence, None

    new_verdict = _VERDICT_TIERS[new_idx]
    # Bumped verdicts get one notch HIGHER confidence (we have direct
    # evidence, not inference)
    conf_order = ["low", "medium", "high"]
    conf_idx = conf_order.index(base_confidence)
    new_confidence = conf_order[min(len(conf_order) - 1, conf_idx + 1)]
    reason = "Verdict bumped: " + " + ".join(reasons)
    return new_verdict, new_confidence, reason


# Layer weights (sum=1.0). LLM weighted highest IF available.
_DEFAULT_WEIGHTS_WITH_LLM = {"regex": 0.20, "statistical": 0.30, "llm": 0.50}
_DEFAULT_WEIGHTS_NO_LLM   = {"regex": 0.40, "statistical": 0.60, "llm": 0.0}


def analyze(text: str,
            use_llm: bool = True,
            weights: Optional[Dict[str, float]] = None) -> AuthorshipReport:
    """Run all 3 layers (LLM optional) and return AuthorshipReport.

    Args:
        text: input string (Vietnamese)
        use_llm: if True, attempt LLM layer; falls back automatically if no key
        weights: optional override of layer weights (must sum to 1.0)
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if len(text.strip()) < 100:
        raise ValueError("Need ≥100 characters for reliable scoring")

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    timestamp = datetime.now().isoformat(timespec="seconds")

    # Layer 1
    regex_score, regex_ev = _scan_regex(text)
    # Layer 2
    profile = _statistical_profile(text)
    stat_score, stat_ev = _score_statistical(profile)
    # Layer 3 (optional)
    llm = _llm_rubric(text) if use_llm else LLMRubric(available=False,
                                                       error="disabled")
    llm_ev = []
    if llm.available:
        for e in llm.evidence:
            llm_ev.append(LayerEvidence(
                layer="llm", rule="claude_rubric", severity="info",
                snippet=e, explanation="Claude rubric evidence",
            ))

    # Choose weights
    if weights is None:
        w = (_DEFAULT_WEIGHTS_WITH_LLM if llm.available
             else _DEFAULT_WEIGHTS_NO_LLM)
    else:
        w = dict(weights)
    # Normalize defensive
    s = sum(w.values()) or 1.0
    w = {k: v / s for k, v in w.items()}

    layer_scores = {
        "regex": regex_score,
        "statistical": stat_score,
        "llm": llm.overall_ai_likelihood if llm.available else 0,
    }

    overall = int(round(
        layer_scores["regex"]       * w.get("regex", 0)
        + layer_scores["statistical"] * w.get("statistical", 0)
        + layer_scores["llm"]         * w.get("llm", 0)
    ))
    overall = max(0, min(100, overall))

    verdict, confidence = _verdict(overall)

    # F1 override: bump verdict when critical/high regex flags stack
    all_regex_ev = regex_ev  # only regex layer flags considered for override
    verdict, confidence, override_reason = _apply_regex_override(
        verdict, confidence, all_regex_ev
    )

    return AuthorshipReport(
        text_hash=text_hash,
        text_length_chars=len(text),
        timestamp_iso=timestamp,
        overall_score=overall,
        verdict=verdict,
        confidence=confidence,
        statistical=profile,
        llm=llm,
        evidence=regex_ev + stat_ev + llm_ev,
        layer_scores=layer_scores,
        layer_weights=w,
        override_reason=override_reason,
    )


# ============================================================
# CLI smoke
# ============================================================

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sample_ai = (
        "Trong thời đại 4.0, chuyển đổi số đã trở nên ngày càng quan trọng "
        "đối với mọi doanh nghiệp. Hôm nay tôi rất hào hứng được chia sẻ "
        "với các bạn một giải pháp toàn diện giúp tối ưu hóa quy trình. "
        "Tuy nhiên, không phải ai cũng hiểu rõ. Do đó, chúng ta cần lưu ý "
        "rằng quy trình này đem lại trải nghiệm tuyệt vời. Ngoài ra, "
        "đáng chú ý là 100% khách hàng hài lòng. Hãy theo dõi để biết thêm!"
    )
    rep = analyze(sample_ai, use_llm=False)
    print(f"verdict: {rep.verdict} | overall: {rep.overall_score} | "
          f"hash: {rep.text_hash[:12]}")
    print(f"layers: {rep.layer_scores}")
    print(f"evidence count: {len(rep.evidence)}")
    for e in rep.evidence[:8]:
        print(f"  [{e.layer}/{e.severity}] {e.rule}: {e.snippet[:80]}")
