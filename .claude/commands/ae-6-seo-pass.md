---
description: Stage 6 — run the 80-item SEO checklist, insert links per budget, generate meta + schema. Voice-damage n-gram check refuses to overwrite if voice drifted.
argument-hint: <slug>
---

# /ae-6-seo-pass

You are running **Stage 6** of the Article Engine pipeline (trainingint.com) for slug: `$ARGUMENTS`.

> Stage 5 is the human edit gate. Confirm with the user that they've finished editing `_draft/03-voice.md` before you proceed. If unsure, ASK — don't assume.

**Authoritative spec:** `docs/superpowers/specs/2026-05-19-article-engine-design.md` §5, §7

## Inputs
- `content/trainingint/$ARGUMENTS/_draft/03-voice.md` (post-human-edit)
- `seo/checklist.md` — the 80+ item canonical checklist
- `seo/link-budget.md` — link rules
- `seo/pillar-map.yaml` — for related blog posts in same/adjacent pillar + course-link assignments
- `src/lib/link-budget.ts` — programmatic validator
- `src/data/courses.json` and the published-log to find existing trainingint.com blog posts for internal linking

## Outputs (write both before declaring success)
1. `content/trainingint/$ARGUMENTS/_draft/04-seo.html`
2. `content/trainingint/$ARGUMENTS/_audit/seo-checklist.md` (per-item pass/fail)

## What `04-seo.html` must contain (vs `03-voice.md`)
- All prose preserved as-is from `03-voice.md` (modulo essential SEO edits — see "voice-damage check" below)
- **Frontmatter additions/refinements**:
  - Final `title` (≤60 chars, primary keyword near front, includes a CTA verb if natural)
  - Final `description` (140–160 chars, includes primary keyword + a CTA verb)
  - `courseLinks` populated per `pillar-map.yaml` (primary trainingint.com course, 1–2 trainingint URLs, 0–1 intellisoft URL)
  - `faqs` array filled (4–8 Q&A — these become FAQPage JSON-LD built by scripts.lib.jsonld)
- **Internal links (trainingint.com siblings):** 2–3 links to sibling blog posts in the same course cluster. Use `href="ae:sibling:<slug>"` placeholders — scripts/wp_publish.py resolves these to live URLs at publish (unresolved siblings are dropped to plain text, never linked broken).
- **Course links:** exactly 1 primary course (the cluster's `course_url`) as an above-fold CTA + a bottom CTA + at most 1 contextual body link (same URL ≤3×). 2–3 secondary courses (from courses/trainingint.yaml `secondary_courses`) as contextual links.
- **Authoritative outbound:** 1–2 (SSG, MOM, HBR, peer-reviewed), `target="_blank" rel="noopener"`, never `rel="sponsored"`.
- **Snippet-bait checks**: TL;DR/answer-first paragraph in first 100 words, table or list under at least one H2, FAQ block present
- **Image alt check**: every image has 8–80 char descriptive alt; hero alt is rich (subjects + setting + tone)
- **Inline images:** reference every inline image as `<img src="ae:img:<filename>" alt="<descriptive alt>">` where `<filename>` is the file in `content/trainingint/$ARGUMENTS/images/` (hero stays the featured image, set at publish). This mirrors the `ae:sibling:` placeholder — scripts/wp_publish.py uploads each referenced image to WP media and rewrites the src to the live URL at publish (spec §8.2). Never emit a raw local path or an un-prefixed remote Pexels URL in the body.
- **Schema:** build JSON-LD via `python -c "from scripts.lib.jsonld import build_jsonld; ..."`; pass `suppress={'FAQPage','BreadcrumbList'}` for any type the active SEO plugin already emits (config/sites.yaml probe.seo_plugin_emits_graph). Embed the returned `<script type="application/ld+json">` block at the end of the HTML body.

## What `seo-checklist.md` must contain
The full 80-item checklist from `seo/checklist.md`, with per-item:
- `[x]` pass / `[ ]` fail / `[~]` partial
- One-line note explaining fails/partials
- A summary at top: total pass / total fail / blockers

## VOICE-DAMAGE CHECK (hard gate — refuse to overwrite if it fires)
Before writing `04-seo.html`:
Compute programmatically: python -c "from scripts.lib.ngram import voice_survival_ratio as v; print(v(open('content/trainingint/$ARGUMENTS/_draft/04-seo.html',encoding='utf-8').read(), open('content/trainingint/$ARGUMENTS/_draft/03-voice.md',encoding='utf-8').read()))". If < 0.85, STOP, show the diff, do not write 04-seo.html.
The SEO pass is for **structure, metadata, links** — it is NOT a rewrite. If you're tempted to rewrite a sentence "for clarity" or "for SEO", don't — that's voice damage.

Acceptable changes that don't trigger the check:
- Adding link anchors over existing text
- Adjusting one phrase to include the primary keyword if it was missing in first 100 words
- Inserting a missing TL;DR paragraph (added, not rewritten)
- Frontmatter / FAQ changes (not body prose)

## Originality gate (must pass)
Run scripts.lib.originality.originality_report(article, open('voice/stories.md').read(), open('voice/stats.md').read(), [open(f).read() for f in glob('content/trainingint/$ARGUMENTS/_research/serp-bodies/*.txt')]). If passes is False, surface to the user — do not paper over.

## Link budget validator
Build the link inventory dict and run scripts.lib.link_budget.validate_links(inv, budget) where budget = config/sites.yaml sites.trainingint.link_budget. If it returns any violations, fix and revalidate before writing 04-seo.html.

## N-GRAM ANTI-PLAGIARISM (hard gate — refuse to write 04-seo.html if it fires)
python -c "from scripts.lib.ngram import overlap_8gram; from glob import glob; a=open('content/trainingint/$ARGUMENTS/_draft/04-seo.html',encoding='utf-8').read(); bad=[(f,overlap_8gram(a,open(f,encoding='utf-8').read())) for f in glob('content/trainingint/$ARGUMENTS/_research/serp-bodies/*.txt')]; bad=[(f,h) for f,h in bad if h]; print('PLAGIARISM:',bad) if bad else print('PASS')"
If any serp-body returns a non-empty overlap list, STOP, name the overlapping 8-word phrase(s), and do NOT write 04-seo.html. (Same contract as ae-8 gate 5.)

## Process
1. Confirm Stage 5 (human edit) is done
2. Read `03-voice.md`, `seo/checklist.md`, `seo/link-budget.md`, `pillar-map.yaml`
3. Identify candidate internal links (other blog posts + courses) and outbound authoritative links
4. Plan all changes (structure, metadata, links) — assemble the candidate `04-seo.html` in memory; do NOT write it yet
5. **Gate 1 — voice-damage:** run `voice_survival_ratio`; if < 0.85, STOP, show the diff, do not write
6. **Gate 2 — n-gram anti-plagiarism:** run `overlap_8gram` vs every `_research/serp-bodies/*.txt`; if any non-empty, STOP, name the phrase, do not write
7. **Gate 3 — link budget:** run `validate_links(inv, budget)`; if any violations, fix and revalidate, do not write
8. **Gate 4 — originality:** run `originality_report(...)`; if `passes` is False, surface to the user, do not write
9. Only if ALL FOUR gates passed, write `04-seo.html`
10. Run the 80-item checklist; write `seo-checklist.md`

## Refuse to proceed if
- Stage 4 output (`03-voice.md`) is missing
- Voice-damage check fails
- Originality gate fails
- Link budget validator returns violations after best-effort placement

After writing, summarize: checklist pass count out of 80, link counts (internal blog / internal course / trainingint / intellisoft / authoritative outbound), originality items present, voice-damage check result.
