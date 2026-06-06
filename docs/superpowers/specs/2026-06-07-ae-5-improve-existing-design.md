# Design: `ae-5-improve-existing` — daily staged article improvement

**Date:** 2026-06-07
**Status:** Design — awaiting review
**Owner:** Vinai

## Problem

Published/scheduled blog articles from the article engine are written once and
left static. SEO, keyword targeting, wording, formatting, and structure all
decay or were never optimal. We want a hands-off daily cadence that researches
and improves a few articles per day, with a human approval gate before anything
goes live.

## Decisions locked (brainstorming 2026-06-07)

- **Autonomy:** Stage for review. Nothing auto-publishes in any phase.
- **Targets:** Live (`published`) + the not-yet-live `scheduled` queue.
- **Dimensions:** (1) content quality (wording/readability/voice), (2) technical
  SEO (schema, meta, internal links, formatting/spacing), (3) keyword ranking
  via GSC. **Imagery is out of scope.**
- **Scheduler:** Windows Task Scheduler (local — where files + WP creds live).
  `/schedule` (cloud) and `/loop` (session-bound) rejected as unfit.
- **Cadence:** 2–3 articles/night (K=2–3).
- **Staging mechanism:** dated git branch + a semantic review digest.

## Reframe that shaped the design

Only **4 of 33 articles are live today**; 29 are future-`scheduled`. So
"improve published articles" alone has a tiny target set. The loop therefore
also polishes scheduled drafts *before* they publish — bigger near-term lever.

## Reuse (already built — do not reinvent)

- `scripts/audit_live.py` — re-fetches a live URL (or audits the artifact body
  for scheduled posts) and re-runs the rendered-page subset of the 80-item
  checklist. **The triage scorer drives this; it is not re-implemented.**
- `scripts/republish.py` — idempotent re-push of a published post.
- `scripts/lib/link_budget.py` — internal-link relevance scoring + budgeting.
- `scripts/lib/ngram.py` — voice-damage n-gram check (refuses voice-drifting
  overwrites).
- `seo/audit-budgets.yaml` — already configured for this pass (it names a
  `blog-5-audit-existing` step): `internal_links_max`, `images_max`,
  `freshness_edits_max`, relevance weights, image targets, external sitemaps.
- `ae-4-voice-pass`, `ae-6-seo-pass`, `ae-8-publish` skills — the creative +
  checklist + publish machinery the improvement pass leans on.

## Architecture — A nests inside C as phases

Approach A (deterministic triage → report) is the foundation. Approach C
(LLM improves the top-K, staged) sits on the same triage engine. Shipping order
de-risks: A first (zero LLM cost/risk, validates scoring), then C.

### Component 1 — `scripts/triage.py` (deterministic; all of Approach A)

Inputs: `status/<site>.yaml`, per-article artifacts, `seo/audit-budgets.yaml`,
optional GSC data.

For each candidate (status in {`published`, `scheduled`}) compute an
**opportunity score** = weighted sum of:

| Signal | Source | Notes |
|---|---|---|
| Audit findings | `audit_live.py` (live for published, artifact for scheduled) | failed checks × severity |
| Internal-link gap | `link_budget.py` vs `internal_links_max` | links missing to budget |
| Freshness age | `last_improved` field in status yaml (new) | days since last improved |
| GSC decay | GSC API (Phase 0) | striking-distance (pos 5–20), position slips, high-impr/low-CTR. **Degrades to 0 if GSC unwired** |

Outputs:
- `status/triage-<site>-<date>.md` — ranked worst-first report listing each
  article's score + specific findings. **This is the Approach-A deliverable.**
- machine-readable ranked top-K list (consumed by Phase 2).

Scoring weights live in `seo/audit-budgets.yaml` (new `triage_weights:` block)
so they're tunable without code edits. Default weights are a starting guess to
be tuned during dogfooding.

### Component 2 — `ae-5-improve-existing` skill (the C layer; LLM)

Input: a slug + its triage findings. Addresses the three in-scope dimensions:

- **Content quality** — tighten wording/readability; apply voice rules (reuse
  `ae-4` + `ngram.py`); strengthen the specific sections triage flagged.
- **Technical SEO** — fix schema/meta; top up internal links via
  `link_budget.py`; fix spacing/heading structure; re-run the 80-item checklist
  (reuse `ae-6`).
- **Keyword ranking** — for GSC striking-distance queries, expand/retarget the
  relevant section + adjust headings/meta.

Guardrails (all pre-existing): voice-damage n-gram refusal; publish gates;
`audit-budgets.yaml` caps (`internal_links_max`, `freshness_edits_max`,
`images_max`). On any guard failure: skip the slug, log, leave no partial stage.

Writes improved `04-seo.html` to **staging only** (see Component 3). Updates
`last_improved` only after a stage is successfully produced.

### Component 3 — staging + review

- Stage to a dated git branch `improve/<date>`; commit changed artifacts there.
  Free rollback; the branch is the source of truth.
- Generate a **semantic digest** `status/review-<date>.md` — not a raw HTML
  diff (too noisy). Each entry reads like:
  > `how-to-filter-data-in-excel`: tightened intro; +3 internal links
  > (pivot/vlookup/charts); fixed FAQ schema; retargeted `excel filter shortcut`
  > (GSC pos 8 → target top-5). Checklist 71 → 78.

You read the digest, approve a subset.

### Component 4 — `scripts/apply_improvement.py <slug…>`

- `published` slug → copy `_improve`→`_draft`, run `republish.py` (live push).
- `scheduled` slug → copy `_improve`→`_draft` only; `ae-8` publishes the
  improved version on its scheduled date (no republish).

### Component 5 — `scripts/nightly_improve.ps1` + Task Scheduler

Daily ~06:00: cd project → activate venv → `triage.py` (always runs) → Phase 2:
`claude -p` headless invoking `ae-5` over top-K → write digest → append log
(`status/nightly-improve.log`). Registered via `schtasks`. Phase 1 deployment
runs the same wrapper minus the `claude -p` step.

## Phasing

- **Phase 0** — one-time GSC API setup (keyword dimension only). Until done,
  triage runs on audit + link + freshness signals; keyword dimension is skipped
  with a note. (Setup can lean on the `claude-seo:seo-google` skill.)
- **Phase 1 (A)** — `triage.py` + nightly report + Task Scheduler. Zero LLM,
  zero risk. Validates scoring; you run existing skills on top picks manually.
- **Phase 2 (C)** — `ae-5` skill + staging + apply script. Nightly auto-prepares
  top-K. 2–3/night over 33 candidates ≈ a 2-week self-rotating cycle (freshness
  aging naturally sinks just-improved articles down the ranking).

## Data model change

Add to each entry in `status/<site>.yaml`:
- `last_improved: <ISO date>` — set when a stage is produced (Phase 2) or an
  improvement is applied. Absent = never improved (ranks high on freshness).

## Risks / edge cases

- **Headless skill invocation** (`claude -p` driving `ae-5`) is the main Phase-2
  unknown. Validate on one article before trusting the nightly job. Fallback:
  a direct Anthropic-API Python step that inlines the improvement prompt.
- **Hard approval gate** — nothing auto-publishes in any phase.
- **Idempotency** — skip any slug with an unapproved `_improve/` already staged
  (don't double-improve pending work).
- **GSC absent** — triage degrades gracefully; keyword dimension no-ops with a
  note, other two dimensions unaffected.
- **Scheduled vs published** — `apply` branches on status (republish only for
  live posts).

## Success criteria

- `triage.py` runs over the current 33 articles; ranking is sane on eyeball;
  report renders.
- `ae-5` on the oldest live article (`how-to-filter-data-in-excel`) produces a
  staged diff + readable digest; voice guard passes; budgets respected.
- `apply_improvement.py` round-trips one live article via `republish.py`.
- Task Scheduler fires the wrapper; log line written.

## Out of scope

- Imagery improvements.
- Auto-publishing without review.
- New-article creation (that's `ae-1..ae-8`).
