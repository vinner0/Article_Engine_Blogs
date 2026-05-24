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
- `scripts/lib/link_budget.py` — programmatic validator
- `courses/trainingint.yaml` + `status/trainingint.yaml` to find existing trainingint.com blog posts (status: scheduled/published) for internal linking

## Outputs (write both before declaring success)
1. `content/trainingint/$ARGUMENTS/_draft/04-seo.html`
2. `content/trainingint/$ARGUMENTS/_audit/seo-checklist.md` (per-item pass/fail)

## What `04-seo.html` must contain (vs `03-voice.md`)
- All prose preserved as-is from `03-voice.md` (modulo essential SEO edits — see "voice-damage check" below)
- **Frontmatter additions/refinements**:
  - Final `title`: core (≤~52 chars, primary keyword near front, comparison/intent modifier + a CTA verb if natural) **then append year + brand from `config/sites.yaml` sites.<site>.seo_title** → `"{core} ({year}) | {brand_suffix}"` when `append_year`. Year is the current year (dynamic, so titles don't go stale). The brand/geo suffix fixes the "geo-blind title" audit finding.
  - Final `description` (140–160 chars, includes primary keyword + a CTA verb)
  - `courseLinks` populated per `pillar-map.yaml` (primary trainingint.com course, 1–2 trainingint URLs, 0–1 intellisoft URL)
  - `faqs` array filled (4–8 Q&A — these become FAQPage JSON-LD built by scripts.lib.jsonld)
- **Internal links (trainingint.com siblings):** 2–3 contextual links to sibling blog posts in the same course cluster. Use `href="ae:sibling:<slug>"` placeholders — scripts/wp_publish.py resolves these to live URLs at publish. Unresolved siblings are dropped to plain text; a token that survives resolution (e.g. status_map not passed) makes publish **refuse** the post (fail-closed gate, scripts/wp_publish.py).
- **Related-Articles block:** near the bottom, a hand-picked block of 3–4 sibling/cluster posts via `scripts.lib.blocks.render_related([(label, "ae:sibling:<slug>"), ...])` (the `ae:sibling:` URLs resolve at publish). This is distinct from the inline contextual links and improves crawl depth + dwell. Aim for **8–12 total internal links** across the post (inline siblings + course links + related block).
- **Course links:** exactly 1 primary course (the cluster's `course_url`) as an above-fold CTA + a bottom CTA + at most 1 contextual body link (same URL ≤3×). 2–3 secondary courses (from courses/trainingint.yaml `secondary_courses`) as contextual links.
- **Styled course card (peak intent):** insert one `scripts.lib.blocks.render_course_card(title, url, funding, cta_label, subtitle)` block at the highest-intent moment (e.g. right after a comparison table or the core how-to). `funding` is the stable badge ("WSQ-funded · SkillsFuture-eligible"); do NOT hardcode price/next-intake (they go stale — the CTA links to the live course page where those are authoritative).
- **Authoritative outbound:** 1–3 (SSG, MOM, HBR, MS Learn, peer-reviewed), `target="_blank" rel="noopener"`, never `rel="sponsored"`.
- **Snippet-bait checks**: TL;DR/answer-first paragraph in first 100 words, table or list under at least one H2, FAQ block present
- **Table of contents:** do NOT hand-author — scripts/wp_publish.py injects a jumplink TOC + adds slug `id` anchors to every `<h2>` at publish for posts with ≥3 H2s (deterministic + idempotent, so it applies uniformly to backfilled and future posts).
- **Image alt check**: every image has 8–80 char **specific** alt — name the actual subject/action + the keyword context (e.g. "VLOOKUP formula matching an order ID across two Excel sheets"), NOT generic stock ("hands typing on a laptop"). Hero alt is rich (subjects + setting + tone). Prefer slug-style, keyword-bearing filenames.
- **Inline images:** reference every inline image as `<img src="ae:img:<filename>" alt="<descriptive alt>">` where `<filename>` is the file in `content/trainingint/$ARGUMENTS/images/` (hero stays the featured image, set at publish). This mirrors the `ae:sibling:` placeholder — scripts/wp_publish.py uploads each referenced image to WP media and rewrites the src to the live URL at publish (spec §8.2). Never emit a raw local path or an un-prefixed remote Pexels URL in the body.
- **Schema:** build JSON-LD via `python -c "from scripts.lib.jsonld import build_jsonld; ..."`; pass `author_same_as=<config sites.<site>.author.same_as>` so the Article author carries E-E-A-T `sameAs` (LinkedIn/YouTube/site). Pass `suppress={'FAQPage','BreadcrumbList','Article'}` for any type the active SEO plugin already emits (config/sites.yaml probe.seo_plugin_emits_graph — for trainingint, Yoast emits Article/Breadcrumb, so `sameAs` is set there in **Yoast → Person**, see the SEO ops checklist). Embed the returned `<script type="application/ld+json">` block at the end of the HTML body. HowTo and Course schema are deliberately NOT emitted (Google deprecated HowTo rich results; Course-on-a-blog-post is a wrong-page signal).

## What `seo-checklist.md` must contain
The full 80-item checklist from `seo/checklist.md`, with per-item:
- `[x]` pass / `[ ]` fail / `[~]` partial
- One-line note explaining fails/partials
- A summary at top: total pass / total fail / blockers

## VOICE-DAMAGE CHECK (hard gate — refuse to overwrite if it fires)
Before writing `04-seo.html`:
Compute programmatically: python -c "from scripts.lib.ngram import voice_survival_ratio as v; print(v(open('content/trainingint/$ARGUMENTS/_draft/04-seo.html',encoding='utf-8').read(), open('content/trainingint/$ARGUMENTS/_draft/03-voice.md',encoding='utf-8').read()))". If < 0.85, STOP, show the diff, delete the candidate `04-seo.html` and STOP.
The SEO pass is for **structure, metadata, links** — it is NOT a rewrite. If you're tempted to rewrite a sentence "for clarity" or "for SEO", don't — that's voice damage.

Acceptable changes that don't trigger the check:
- Adding link anchors over existing text
- Adjusting one phrase to include the primary keyword if it was missing in first 100 words
- Inserting a missing TL;DR paragraph (added, not rewritten)
- Frontmatter / FAQ changes (not body prose)

## Originality gate (must pass)
Run scripts.lib.originality.originality_report(article, open('voice/stories.md').read(), open('voice/stats.md').read(), [open(f).read() for f in glob('content/trainingint/$ARGUMENTS/_research/serp-bodies/*.txt')]). If passes is False, surface to the user — do not paper over.

## Link budget validator
Build the link inventory dict and run scripts.lib.link_budget.validate_links(inv, budget) where budget = config/sites.yaml sites.trainingint.link_budget. If it returns any violations, fix and re-validate before the file stands.

## N-GRAM ANTI-PLAGIARISM (hard gate — refuse to write 04-seo.html if it fires)
python -c "from scripts.lib.ngram import overlap_8gram; from glob import glob; a=open('content/trainingint/$ARGUMENTS/_draft/04-seo.html',encoding='utf-8').read(); bad=[(f,overlap_8gram(a,open(f,encoding='utf-8').read())) for f in glob('content/trainingint/$ARGUMENTS/_research/serp-bodies/*.txt')]; bad=[(f,h) for f,h in bad if h]; print('PLAGIARISM:',bad) if bad else print('PASS')"
If any serp-body returns a non-empty overlap list, STOP, name the overlapping 8-word phrase(s), and delete the candidate `04-seo.html` and STOP. (Same contract as ae-8 gate 5.)

## Process
1. Confirm Stage 5 (human edit) is done
2. Read `03-voice.md`, `seo/checklist.md`, `seo/link-budget.md`, `pillar-map.yaml`
3. Identify candidate internal links (other blog posts + courses) and outbound authoritative links
4. Plan all changes (structure, metadata, links) and **WRITE the candidate `04-seo.html`** (the gates below read it from disk; it is provisional until all gates pass)
5. **Gate 1 — voice-damage:** run `voice_survival_ratio`; if < 0.85: delete the candidate `04-seo.html`, show the diff, STOP
6. **Gate 2 — n-gram anti-plagiarism:** run `overlap_8gram` vs every `_research/serp-bodies/*.txt`; if any non-empty: delete the candidate `04-seo.html`, name the phrase, STOP
7. **Gate 3 — link budget:** run `validate_links(inv, budget)`; if any violations: fix and re-write the candidate, then re-run gates 1-3 (do not proceed with a violating file)
8. **Gate 4 — originality:** run `originality_report(...)`; if `passes` is False: delete the candidate `04-seo.html`, surface to the user, STOP
9. All four gates passed → `04-seo.html` stands (already on disk)
10. Run the 80-item checklist; write `_audit/seo-checklist.md`

## Refuse to proceed if
- Stage 4 output (`03-voice.md`) is missing
- Voice-damage check fails
- Originality gate fails
- Link budget validator returns violations after best-effort placement

After writing, summarize: checklist pass count out of 80, link counts (internal blog / internal course / trainingint / intellisoft / authoritative outbound), originality items present, voice-damage check result.
