---
description: Drive 5–15 slugs through ae-1..ae-4, stop at the human review gate.
argument-hint: <course-id | comma-separated slugs>
---

# /ae-batch

Batch for `$ARGUMENTS` on trainingint.com.

## Process
1. Resolve slugs: if a course id, take that course's `status: idea` slugs from
   courses/trainingint.yaml (SKIP `status: proposed` — quarantined per spec §6). Cap 15.
2. Per slug in order: /ae-1 → /ae-2 → /ae-3 → /ae-4. Parallel sub-agents per slug
   where independent (softskills pattern). Each stage writes its artifact before next; resumable.
3. **STOP at the human review gate.** Print a table: slug | title | primary_keyword |
   content/trainingint/<slug>/_draft/03-voice.md. Tell the owner: edit each 03-voice.md;
   then per accepted slug run /ae-6-seo-pass <slug> then /ae-8-publish <slug>.
4. Do NOT run /ae-6 or /ae-8 automatically — those are post-review.

## Warn (don't block research) if config/sites.yaml probe.rest_ok != true:
publishing is blocked until scripts/probe.py passes; research/draft may still proceed.
