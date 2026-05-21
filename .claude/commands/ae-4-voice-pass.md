---
description: Stage 4 — rewrite the draft in Vinai's voice (analogies, stories, opinions, stats, SG-aware framing). Preserves structure. Logs which voice rules fired where.
argument-hint: <slug>
---

# /ae-4-voice-pass

You are running **Stage 4** of the Article Engine pipeline (trainingint.com) for slug: `$ARGUMENTS`.

**Authoritative spec:** `docs/superpowers/specs/2026-05-19-article-engine-design.md` §5, §6

## Inputs
- `content/trainingint/$ARGUMENTS/_draft/02-draft.md` (Stage 3)
- All files in `voice/`:
  - `voice/voice.md` — tone, sentence rhythm, persona (patient teacher, 24 years SG training)
  - `voice/humor.md` — what's funny + what's banned (no dad jokes, no edgy)
  - `voice/opinions.md` — Vinai's stances (drop in where they fit; don't shoehorn)
  - `voice/stats.md` — **locked content, verbatim only** (24 years, 48,000+ professionals, 12,600+ companies, 27 WSQ courses, etc. — never paraphrase, never invent)
  - `voice/stories.md` — 8–15 anecdotes tagged by topic; pick 1–2 that fit the post
  - `voice/do-not-write.md` — banned phrases, AI tells, clichés to scrub

## Output
`content/trainingint/$ARGUMENTS/_draft/03-voice.md`

Plus a `## Voice rule log` section at the **end of the file** (kept inside the file as a comment block or HTML comment so it doesn't render) listing which rule fired where:
```
<!-- VOICE_RULES_FIRED
- Analogy injected at H2 #2 ("60-second pre-meeting ritual"): "like a notebook with pages"
- Story from stories.md tagged "presentation-anxiety" at H2 #4
- Stat verbatim from stats.md ("24 years training in Singapore") at intro
- SG-aware framing at H2 #6 ("WSQ-funded, ACTA-certified")
- Banned phrase scrubbed: "in today's fast-paced world" → rewritten
-->
```

## What "applying voice" means
**Mandatory injections** (every post):
- ≥1 analogy (Vinai's signature move — "X is like Y" framing). Analogies must be original; check against top-3 SERP via memory of `serp.md`.
- ≥1 verbatim stat from `stats.md`. **Never paraphrase these stats. Never invent new ones.** If the stat doesn't fit the post, just skip — don't fabricate a fitting one.
- ≥1 story from `stories.md` if a tag matches the post's topic. If no tag matches, skip rather than force-fitting.
- Singapore-aware framing where natural (A4 not letter, WSQ, SkillsFuture, MOM, local working culture)
- Closing pattern: "I hope you'll like this" / "do try it out" / "give it a try" + concrete next-action (matches Vinai's signature close)

**Sentence rhythm**: short imperatives ("Press enter.") then longer explanatory sentences. Mix lengths. Don't write all 25-word sentences.

**Mild enthusiasm sparingly**: "how good is that?", "fantastic", "extremely easy" — once or twice per post, not every paragraph.

**Manager/boss framing**: connect concepts to a real workplace pain. Vinai writes for working professionals, not students.

## Banned (override anything else)
Scrub all of these from the draft:
- "in today's fast-paced world", "delve", "leverage", "in this comprehensive guide", "unlock your potential", "navigate the complexities of", "whether you're a X or a Y", "let's dive in", "let's dive deep", "it's no secret that"
- Em-dash overuse (>3 per 500 words = too many)
- Dad jokes, snark, edgy humor, anything that punches down
- Anything in `voice/do-not-write.md` (read it before starting)

## Preserve from the draft
- All H1 / H2 / H3 structure exactly
- All cluster keywords (don't drop them while rewriting)
- All placeholder slots (AuthorBio, CourseCTA, TableOfContents, RelatedPosts) — these are inline markers, not MDX components; `scripts/wp_publish.py` resolves them at publish
- Frontmatter at top — copy verbatim
- Image references (`heroImage`, inline `![](...)`)
- Course links + internal links (Stage 6 will rebalance, but don't drop them)
- FAQ Q&A — rewrite the prose in voice but keep the Q text and the answer's substantive points

## Process
1. Read all of `voice/`
2. Read `_draft/02-draft.md`
3. Pass through section by section. Within each section: scrub banned phrases → adjust rhythm → inject mandatory voice elements where natural → log what fired
4. Read `voice/do-not-write.md` once more after; do a final scrub pass
5. Write `03-voice.md` with the rule log block at the end

## Refuse to proceed if
- Stage 3 hasn't completed (`02-draft.md` missing)
- `voice/stats.md` or `voice/do-not-write.md` is empty (escalate to Vinai — the voice corpus needs to exist before voice pass works)

After writing, summarize: which mandatory injections happened, which were skipped (and why), how many banned phrases were scrubbed, total length delta vs draft. **Tell the user clearly: "This is now ready for Stage 5 — your human edit gate. Read 03-voice.md, edit in place, then run /ae-6-seo-pass when satisfied."**
