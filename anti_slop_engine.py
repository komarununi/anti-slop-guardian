"""
Komaru Anti-Slop Guardian — Pure-Regex Engine
==============================================

NO LLM. NO API call. NO opaque "AI detection".
Just transparent regex + counting + thresholds.

Why: trust + speed + zero cost. Users can audit every flag.

Engine API:
    engine = AntiSlopEngine(tier="free")
    flags = engine.analyze(text)
    # → list of Flag dicts with rule, snippet, severity, suggestion
"""

import re
import statistics
from typing import List, Dict, Optional
from patterns import BANNED_PHRASES, STRUCTURAL_RULES, UI_LIMITS, TIER_ACCESS


class AntiSlopEngine:
    """Pure-regex Anti-Slop pattern detection engine."""

    def __init__(self, tier: str = "free"):
        if tier not in TIER_ACCESS:
            raise ValueError(f"Unknown tier: {tier}. Valid: {list(TIER_ACCESS.keys())}")
        self.tier = tier
        self.tier_config = TIER_ACCESS[tier]
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex per tier filter for performance."""
        allowed_cats = set(self.tier_config["categories"])
        allowed_sevs = set(self.tier_config["severities"])

        self.active_phrases = [
            {**p, "compiled": re.compile(p["pattern"], re.IGNORECASE)}
            for p in BANNED_PHRASES
            if p["category"] in allowed_cats and p["severity"] in allowed_sevs
        ]

        self.active_structural = [
            r for r in STRUCTURAL_RULES
            if "structure" in allowed_cats or "density" in allowed_cats
        ]

    # ---------- Public API ----------

    def analyze(self, text: str) -> Dict:
        """
        Run all enabled patterns on text. Return dict:
            {
                "flags": [Flag, ...],
                "stats": {"char_count": ..., "word_count": ..., "para_count": ...},
                "summary": {"total": ..., "by_severity": {...}, "by_category": {...}},
                "tier": "free",
                "filtered_count": N (patterns disabled by tier),
            }
        """
        if not text or len(text.strip()) < UI_LIMITS["min_chars_for_filter"]:
            return self._empty_result(text, reason="too_short")

        if len(text) > UI_LIMITS["max_chars_hard_limit"]:
            return self._empty_result(text, reason="too_long")

        flags = []
        flags.extend(self._scan_phrases(text))

        if "structure" in self.tier_config["categories"]:
            flags.extend(self._scan_structural(text))

        return {
            "flags": flags,
            "stats": self._compute_stats(text),
            "summary": self._summarize(flags),
            "tier": self.tier,
            "filtered_count": len(BANNED_PHRASES) - len(self.active_phrases),
        }

    # ---------- Phrase scanning ----------

    def _scan_phrases(self, text: str) -> List[Dict]:
        """Find all banned-phrase matches with context snippets."""
        found = []
        for phrase in self.active_phrases:
            for match in phrase["compiled"].finditer(text):
                snippet = self._extract_snippet(text, match.start(), match.end())
                found.append({
                    "rule": phrase["rule"],
                    "category": phrase["category"],
                    "severity": phrase["severity"],
                    "match": match.group(),
                    "snippet": snippet,
                    "position": match.start(),
                    "suggestion": phrase["replacement"],
                    "why": phrase["why"],
                })
        return found

    def _extract_snippet(self, text: str, start: int, end: int, ctx: int = 40) -> str:
        """Get ±ctx chars around match, with ellipsis if truncated."""
        s = max(0, start - ctx)
        e = min(len(text), end + ctx)
        prefix = "…" if s > 0 else ""
        suffix = "…" if e < len(text) else ""
        return f"{prefix}{text[s:e]}{suffix}"

    # ---------- Structural scanning ----------

    def _scan_structural(self, text: str) -> List[Dict]:
        """Run structural heuristics (em-dash density, paragraph openers, etc)."""
        flags = []

        # Em-dash density
        em_dash_count = text.count("—") + text.count("–")
        per_1000 = (em_dash_count / max(len(text), 1)) * 1000
        if per_1000 >= 5.0:
            flags.append(self._mk_structural_flag(
                "em_dash_density", "high",
                f"{em_dash_count} em-dashes ({per_1000:.1f}/1000 chars) — well above natural rate",
                "Replace some with periods or commas. Keep <3 per 1000 chars in body voice."
            ))
        elif per_1000 >= 3.0:
            flags.append(self._mk_structural_flag(
                "em_dash_density", "medium",
                f"{em_dash_count} em-dashes ({per_1000:.1f}/1000 chars) — slightly elevated",
                "Trim a few. Em-dashes work best sparingly."
            ))

        # Paragraph "The" opener ratio
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if len(paras) >= 3:
            the_starters = sum(1 for p in paras if re.match(r"^(?:The|This)\b", p))
            ratio = the_starters / len(paras)
            if ratio >= 0.7:
                flags.append(self._mk_structural_flag(
                    "the_paragraph_opener", "high",
                    f"{the_starters}/{len(paras)} paragraphs start with 'The/This' ({ratio:.0%})",
                    "Vary openers. Use names, fragments, questions, transitions."
                ))
            elif ratio >= 0.5:
                flags.append(self._mk_structural_flag(
                    "the_paragraph_opener", "medium",
                    f"{the_starters}/{len(paras)} paragraphs start with 'The/This' ({ratio:.0%})",
                    "Mix it up. ≥3 different opener types feels more human."
                ))

        # Consecutive "The..." sentence starts
        sentences = re.split(r"(?<=[.!?])\s+", text)
        max_run = current_run = 0
        for s in sentences:
            if re.match(r"^(?:The|This)\b", s.strip()):
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0
        if max_run >= 4:
            flags.append(self._mk_structural_flag(
                "consecutive_the_sentences", "critical",
                f"{max_run} consecutive sentences start with 'The/This'",
                "Break the run with subject swap, fragment, or question."
            ))
        elif max_run >= 3:
            flags.append(self._mk_structural_flag(
                "consecutive_the_sentences", "high",
                f"{max_run} consecutive sentences start with 'The/This'",
                "Break the run for rhythm."
            ))

        # Parallel triples ("X, Y, and Z")
        triple_pattern = re.compile(r"\b(\w+),\s+(\w+),?\s+and\s+(\w+)\b")
        triples = triple_pattern.findall(text)
        word_count = len(text.split())
        triples_per_1000 = (len(triples) / max(word_count, 1)) * 1000
        if triples_per_1000 >= 8.0:
            flags.append(self._mk_structural_flag(
                "parallel_triples", "high",
                f"{len(triples)} 'X, Y, and Z' patterns ({triples_per_1000:.1f}/1000 words)",
                "Mix in 2-item lists or 4-item lists. Real writing varies."
            ))
        elif triples_per_1000 >= 4.0:
            flags.append(self._mk_structural_flag(
                "parallel_triples", "medium",
                f"{len(triples)} parallel triples ({triples_per_1000:.1f}/1000 words)",
                "Slightly elevated. Vary list length."
            ))

        # Sentence length variance
        if len(sentences) >= 5:
            lengths = [len(s.split()) for s in sentences if s.strip()]
            if lengths:
                stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0
                if stdev < 4.0:
                    flags.append(self._mk_structural_flag(
                        "uniform_sentence_length", "low",
                        f"Sentence length stdev={stdev:.1f} (low variance, AI-flat)",
                        "Add 1-2 short sentences (<10 words) for rhythm."
                    ))

        return flags

    def _mk_structural_flag(self, rule: str, severity: str, summary: str, fix: str) -> Dict:
        return {
            "rule": rule,
            "category": "structure",
            "severity": severity,
            "match": summary,
            "snippet": summary,
            "position": -1,
            "suggestion": fix,
            "why": next((r["why"] for r in STRUCTURAL_RULES if r["rule"] == rule), ""),
        }

    # ---------- Stats / summary ----------

    def _compute_stats(self, text: str) -> Dict:
        return {
            "char_count": len(text),
            "word_count": len(text.split()),
            "para_count": len([p for p in re.split(r"\n\s*\n", text) if p.strip()]),
            "sentence_count": len(re.split(r"(?<=[.!?])\s+", text)),
        }

    def _summarize(self, flags: List[Dict]) -> Dict:
        by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_cat = {"phrase": 0, "structure": 0, "density": 0}
        for f in flags:
            by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
            by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1
        return {
            "total": len(flags),
            "by_severity": by_sev,
            "by_category": by_cat,
        }

    def _empty_result(self, text: str, reason: str) -> Dict:
        return {
            "flags": [],
            "stats": self._compute_stats(text) if text else {},
            "summary": {"total": 0, "by_severity": {}, "by_category": {}},
            "tier": self.tier,
            "filtered_count": 0,
            "skip_reason": reason,
        }


# ---------- Module-level convenience ----------

def quick_check(text: str, tier: str = "free") -> Dict:
    """One-shot helper for testing."""
    engine = AntiSlopEngine(tier=tier)
    return engine.analyze(text)


if __name__ == "__main__":
    # Smoke test
    sample = """
This paper will delve into the multifaceted nature of AI-generated text.
It is important to note that the findings reveal groundbreaking patterns.
The intricate tapestry of language underscores the importance of detection.
The methodology leverages comprehensive analysis. The results are robust.
The conclusion shows that we navigate the landscape of slop carefully.
"""
    result = quick_check(sample, tier="pro")
    print(f"Flags found: {result['summary']['total']}")
    print(f"By severity: {result['summary']['by_severity']}")
    for f in result["flags"]:
        print(f"  [{f['severity']}] {f['rule']}: {f['match']}")
