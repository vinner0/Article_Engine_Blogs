---
description: Stage 1 — keyword cluster + SERP intent for a blog post. Validates volume/difficulty, classifies intent, flags wrong-format-for-SERP.
argument-hint: <slug>
---

# /blog-1-keyword-research

You are running **Stage 1** of the Article Engine pipeline (trainingint.com) for slug: `$ARGUMENTS`.

**Authoritative spec:** `docs/superpowers/specs/2026-05-19-article-engine-design.md` §5

## Inputs
- The slug `$ARGUMENTS`
- The pillar/cluster assignment from `courses/trainingint.yaml` — read it and find the entry for this slug to get the **primary keyword**, pillar (P1–P5), and any pre-assigned course-link target
- An Ubersuggest CSV if the user pasted one (look for it in the conversation; otherwise ask the user to paste keyword data)

## Outputs (write both before declaring success)
1. `content/trainingint/$ARGUMENTS/_research/cluster.md`
2. `content/trainingint/$ARGUMENTS/_research/intent.md`

If the slug folder doesn't exist, create it.

## What `cluster.md` must contain
- The primary keyword (1)
- 5–15 secondary keywords (semantic variations, long-tail, question forms, "how to" / "what is" / "best" framings)
- For each keyword: estimated search volume, keyword difficulty (KD), and search intent (informational / commercial / transactional / navigational)
- **Validation gate**: every secondary keyword must have volume ≥30 AND KD ≤25. Flag any that fail with `[REJECTED]` and a one-line reason. If <5 pass, escalate to the user with proposed swaps from the pillar's backup list.
- A "Cluster coverage" section: which keywords will be primary H2 sections, which become FAQ Q&A, which are passing mentions in body prose

## What `intent.md` must contain
- **SERP intent classification** for the primary keyword (informational / commercial / transactional / mixed). Be explicit; cite which top-3 results signal which intent.
- **SERP features present** (featured snippet, People Also Ask, video carousel, image pack, knowledge panel, local pack). Each feature is an opportunity (snippet bait) or a warning (video → blog may be wrong format).
- **Format-fit check**: does Google rank long-form articles for this query, or videos / calculators / listicles / forum threads? If non-article, **STOP and flag to user** — recommend either pivoting format or picking a different cluster keyword.
- **Recommended primary H1 framing** based on what's currently ranking (don't be original here; match what wins).

## Process
1. Read `courses/trainingint.yaml` to get the primary keyword + pillar context
2. If the user pasted an Ubersuggest CSV, parse it; otherwise ask for it (don't fabricate keyword data)
4. Run the validation gates; surface rejections clearly
5. Write both files; confirm by listing them

## Refuse to proceed if
- The slug isn't in `courses/trainingint.yaml` (instruct user to add it first; pipeline depends on the source-of-truth registry)
- No keyword data is available and user can't supply it (don't hallucinate volumes / KD)
- SERP format is non-article (flag and stop; don't waste downstream stages on a wrong-format target)

After writing both files, summarize in 3–5 lines: primary keyword, # secondary kws passing the gate, intent classification, format-fit verdict, and the one-line recommendation for the H1.
