---
description: Stage 2 — fetch top-3 ranking pages and extract the structural target (word count, H2 pattern, format, what they cover and miss).
argument-hint: <slug>
---

# /blog-2-serp-analyze

You are running **Stage 2** of the Article Engine pipeline (trainingint.com) for slug: `$ARGUMENTS`.

**Authoritative spec:** `docs/superpowers/specs/2026-05-19-article-engine-design.md` §5

## Inputs
- The primary keyword from `content/trainingint/$ARGUMENTS/_research/cluster.md` (Stage 1 must have run; refuse if it hasn't)
- WebFetch / WebSearch tools to retrieve the top-3 organic results

## Output
Single file: `content/trainingint/$ARGUMENTS/_research/serp.md`

## What `serp.md` must contain
1. **Top-3 organic results** for the primary keyword (search Google directly; **exclude Reddit, Quora, YouTube, and trainingint.com itself**). For each: URL, page title, meta description.
2. **Per-result extraction**:
   - Word count (estimate from text content)
   - H2 count + the actual H2 titles (verbatim)
   - Image count (rough)
   - Format pattern (numbered listicle / how-to guide / definition + tactics / case study / hybrid)
   - 3–5 things they cover well
   - 3–5 things they miss or cover poorly (this is your differentiation surface)
3. **Aggregate structural target** for our post:
   - Recommended word count (median of top-3, ±15%)
   - Recommended H2 count and a draft H2 outline that combines the best of what they cover + what they miss
   - Format pattern to adopt
   - Image budget (hero + N inline)
   - **Differentiation thesis** in one sentence: what makes our post worth ranking over theirs (must include something only Vinai/trainingint.com can plausibly say — e.g. Singapore/WSQ angle, training-room story, original framework)

## Process
1. Read the primary keyword from `_research/cluster.md`
2. Use WebSearch to find top-10, then filter out Reddit/Quora/YouTube/trainingint.com, take top-3
3. WebFetch each; extract structure (don't quote large blocks of their prose — we're stealing structure, not content)
5. Write `serp.md`; summarize the differentiation thesis to the user

## Refuse to proceed if
- Stage 1 hasn't run (no `cluster.md`)
- All three top-3 results are the same format that's a poor fit for blog (e.g. 3 YouTube videos surface above any article — that should have been caught at Stage 1; surface back)
- WebFetch fails for ≥2 of 3 (escalate to user; don't fabricate competitor data)

After writing, summarize in 3–5 lines: median word count target, H2 count target, format, top-3 URLs, and the differentiation thesis.


## Additional output (Article Engine)
Also write `content/trainingint/$ARGUMENTS/_research/serp-bodies/{1,2,3}.txt` — the full extracted body text of the top-3 results. Required input for the /ae-6 originality + n-gram gates.
