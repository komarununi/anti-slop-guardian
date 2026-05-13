# VN Samples — Validation Findings (2026-05-13)

5 representative VN text categories run through engine + suggestions module.
This document captures **calibration findings** for post-W2 retro, NOT test
failures.

## Pass/Fail summary

| Sample | Verdict | Overall | Suggestions | Note |
|--------|---------|---------|-------------|------|
| 01 FB ad (AI-heavy) | `mixed` | 40/100 | 9 (1C/6H/2M) | ⚠️ Verdict under-weight |
| 02 Personal blog (human) | `human` | 0/100 | 0 | ✅ Clean negative |
| 03 Mixed polished blog | `human` | 5/100 | 1M | ✅ Borderline → human (good) |
| 04 CSKH auto-reply | `mixed` | 40/100 | 6 (3H/2M/1L) | ⚠️ Verdict under-weight |
| 05 Academic abstract | `human` | 6/100 | 1L | ✅ Formal connectors flagged low |

## ✅ RESOLVED 2026-05-13 — Finding F1 fixed via verdict override

Override rule shipped in `vn_origin_engine._apply_regex_override`:
- ≥1 critical regex flag → bump verdict 1 tier (floor "likely_ai")
- ≥3 high regex flags → bump verdict 1 tier (floor "likely_ai")
- Both conditions → bump 2 tiers
- Confidence bumped 1 notch on any override
- Override reason recorded in `AuthorshipReport.override_reason`

Post-fix sample verdicts:
- Sample 01 (FB ad): `mixed` → `very_likely_ai` (1 critical + 6 high)
- Sample 04 (CSKH reply): `mixed` → `likely_ai` (3 high)
- Sample 02/03/05: unchanged (no override triggered)

10 new tests in `test_vn_origin.py` cover override matrix.

## Finding F1 (original report — kept for context) — Regex-heavy AI text under-weights to "mixed"

**Observed:** Samples 01 and 04 trigger 9-6 regex flags including
critical-tier opener templates and high-tier translationese, scoring
`regex=100/100`. But overall = 100 × 0.40 + 0 × 0.60 = **40 → "mixed"**.

**Implication:** Users with obvious AI text may see "🟡 Có dấu hiệu nhẹ" when
the right label is "🟠 Nhiều dấu hiệu" or "🔴 Dấu hiệu rõ rệt".

**Possible fixes (decide post-W2):**
1. Rebalance no-LLM weights: `{regex: 0.55, statistical: 0.45}` → AI ad
   would score 55 → `likely_ai`.
2. Add **flag-count override**: if ≥1 critical OR ≥3 high regex flags → bump
   verdict by one tier regardless of weighted score.
3. Make statistical layer more sensitive (current thresholds may be too
   conservative for short marketing copy).

**Recommended:** Option 2 (override) — preserves weighted-score nuance for
borderline cases while ensuring stacked critical AI signatures don't
fall through.

## Finding F2 — Statistical layer dormant on short texts

Samples 01 and 04 score `statistical=0/100` despite obvious AI flavor. Root
cause: 300-400 word samples don't trigger burstiness/TTR thresholds because
the statistical features need ~500+ words to stabilize.

**Implication:** Short marketing copy (FB ad, CSKH reply, LinkedIn post) is
the typical user case but is exactly where the statistical layer is weakest.

**Possible fixes:**
- Adjust thresholds for short-text mode (`<500 words`)
- Add **density-normalized** statistical scoring (per 100w rather than
  absolute)
- Document that short-text scoring leans heavily on regex layer

## Finding F3 — Academic text correctly under-flagged

Sample 05 (academic abstract) only triggers 1 low-tier flag (sentence
length in AI band). This is **correct behavior**: academic writing
intentionally uses formal connectors, consistent sentence rhythm, and
paragraph structure. The engine respects this by not flagging
high-severity on these signals alone.

**Implication:** Tool works as intended for academic/technical writers —
they won't get spammed with false positives. Confirms the writing-quality
framing (not forensic).

## Finding F4 — Suggestions module surfaces actionable rewrites

For all flagged samples, the suggestion module produces specific rewrite
hints with example snippets. Manual review of top 5 suggestions per
sample: all are actionable, none are vague filler.

**Example (Sample 01 critical):**
```
[critical] VO01 — Hôm nay tôi rất hào hứng
Gợi ý: Vào thẳng: nói cái gì + tại sao đáng đọc
Ví dụ: "Hôm nay tôi rất hào hứng được chia sẻ với các bạn..."
```

This is the value-add of the suggestions module over raw evidence list.

## Next actions (post-W2)

- [ ] Decide F1 fix approach (override vs reweight)
- [ ] Tune F2 short-text thresholds OR document explicit short-text caveat
- [ ] Add 5 more VN samples per category once Pro launches and we have real
      user data (current samples are author-written)
- [ ] Consider adding LinkedIn-VN specific patterns (different from FB ad)
