---
description: Drive 5–15 slugs through ae-1..ae-4, stop at the human review gate.
argument-hint: <course-id | comma-separated slugs>
---

# /ae-batch

Batch for `$ARGUMENTS` on trainingint.com.

## Process
1. **Resolve slugs.** If a course id, take that course's `status: idea` slugs from
   `courses/trainingint.yaml` (SKIP `status: proposed` — quarantined per spec §6). Cap 15.
   **Then cross-reference `status/trainingint.yaml` and SKIP any slug already at
   `status: scheduled` or `status: published`** — `ae-8-publish` writes there without
   updating `courses/*.yaml`, so the `idea` flag in courses is stale for already-shipped
   slugs. Print one line per skip: `skipped (already scheduled): <slug>`.
2. **Slugs run concurrently as one sub-agent per slug (softskills batch pattern); stages
   WITHIN a slug run sequentially** /ae-1 → /ae-2 → /ae-3 → /ae-4 (each stage writes its
   artifact before the next; resumable). Slugs are independent so their sub-agents do not
   share state. If sub-agent fan-out is unavailable, fall back to sequential per slug.

   **CRITICAL — anti-stop language for every sub-agent prompt (must include verbatim):**
   > Each skill's final output is INTERMEDIATE, not a stopping signal. After /ae-1 returns
   > its report, immediately invoke /ae-2. After /ae-2 returns, immediately invoke /ae-3.
   > After /ae-3 returns, immediately invoke /ae-4. Only produce YOUR final report after
   > /ae-4 has written `_draft/03-voice.md`. A skill completing is NOT the end of your task.

   Without this, sub-agents reliably stall after /ae-1 (observed 3/5 in the copilot batch).
3. **STOP at the human review gate.** Print a table: slug | title | primary_keyword |
   content/trainingint/<slug>/_draft/03-voice.md. Tell the owner: edit each 03-voice.md;
   then per accepted slug run /ae-6-seo-pass <slug> then /ae-8-publish <slug>.
4. **Post-fan-out verification.** Before declaring batch done, check `_draft/03-voice.md`
   exists for every dispatched slug. Auto-re-dispatch any slug missing it (same anti-stop
   prompt). Do NOT rely on the user to spot a stalled slug.
5. Do NOT run /ae-6 or /ae-8 automatically — those are post-review.

## Warn (don't block research) if config/sites.yaml probe.rest_ok != true:
publishing is blocked until scripts/probe.py passes; research/draft may still proceed.
