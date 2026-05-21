---
description: Stage 3 — two-step draft. Skeleton (H1/H2 outline) for review, then full draft. Pulls Pexels images. Voice is NOT yet applied.
argument-hint: <slug>
---

# /ae-3-draft

You are running **Stage 3** of the Article Engine pipeline (trainingint.com) for slug: `$ARGUMENTS`.

**Authoritative spec:** `docs/superpowers/specs/2026-05-19-article-engine-design.md` §5

## Inputs
- `content/trainingint/$ARGUMENTS/_research/cluster.md` (Stage 1)
- `content/trainingint/$ARGUMENTS/_research/serp.md` (Stage 2)
- `voice/` folder for tone signals (but **do not yet inject voice rewrites** — that's Stage 4)
- Pexels API key from `.env` for image fetching

## Outputs (two-step — pause for user review between)
1. **Step A:** `content/trainingint/$ARGUMENTS/_draft/01-skeleton.md` — show to user, **wait for their go-ahead** before writing Step B
2. **Step B:** `content/trainingint/$ARGUMENTS/_draft/02-draft.md` — full draft against approved skeleton

If the user requests skeleton edits, update `01-skeleton.md` and re-confirm before proceeding to Step B.

## What `01-skeleton.md` must contain
- **H1** (≤60 chars, primary keyword near front, matches SERP intent recommendation from Stage 1)
- **TL;DR / answer-first paragraph** placeholder (snippet bait — 40–60 words, directly answers the primary query)
- **4–8 H2 sections** with one-line description of what each covers + which cluster keywords it targets
- **FAQ block placeholder** with 4–8 Q&A slots (questions drawn from PAA in `intent.md` + cluster long-tails)
- **CourseCTA placement** — which course is the primary lead capture? (read `courses/trainingint.yaml`: use the cluster `course_url` as the primary CourseCTA and `secondary_courses` for supporting links)
- **AuthorBio + RelatedPosts** at the end (these are auto-injected by `BlogLayout`, but mark the slot)
- **Image slots**: hero + 0–4 inline. For each, write a one-sentence Pexels search query (specific, e.g. "Singapore office colleagues conference room laptop").

## What `02-draft.md` must contain
- Full prose under each H2, hitting the recommended word count from Stage 2 (±15%)
- Primary keyword in first 100 words; secondary cluster keywords distributed naturally across H2s
- Numbered steps / bullet lists / tables where format-appropriate (snippet bait)
- All FAQ Q&A filled in (treat each A as 50–120 words, plain answer first then nuance)
- CourseCTA + AuthorBio slots marked as inline HTML/markdown placeholders that `scripts/wp_publish.py` resolves at publish (no MDX — the WP target is plain HTML)
- Hero + inline images downloaded via `python scripts/fetch_pexels_inline.py <slug>` (uses `PEXELS_API_KEY` from `.env`) and saved under `content/trainingint/$ARGUMENTS/images/`. Use the queries from the skeleton.
- Frontmatter at top of file (YAML): title, description, primaryKeyword, keywordCluster, pillar, cluster, publishedAt, heroImage, heroAlt, readingTime, courseLinks, faqs
- **Voice is NOT yet applied** — write clean, competent, generic prose. Stage 4 (`/ae-4-voice-pass`) injects Vinai's voice. If you write voice now, you'll fight Stage 4.

## Process
1. Read `cluster.md` and `serp.md`; read `courses/trainingint.yaml` for the course-link assignment; read `voice/voice.md` and `voice/do-not-write.md` for **what to avoid** (no AI tells, no banned phrases — but no positive voice injection)
2. Write `01-skeleton.md`; show to user; wait for sign-off
3. Once approved, fetch Pexels images: `python scripts/fetch_pexels_inline.py $ARGUMENTS`. Save to `images/`.
4. Write `02-draft.md` with frontmatter, prose, placeholder slots, image references
6. Confirm reading time roughly matches target word count

## Refuse to proceed if
- Stages 1 or 2 haven't run
- Pexels API call fails (escalate; don't ship without hero image)
- Word count target is unrealistic given the cluster (push back, suggest splitting into two posts)

After Step A, summarize the skeleton in 5–8 lines and explicitly ask "Ready to write the full draft?". After Step B, summarize: word count, image count, frontmatter validation pass/fail.
