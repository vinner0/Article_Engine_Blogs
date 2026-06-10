# Design: Legacy Article Improvement Engine (trainingint.com)

**Date:** 2026-06-09
**Status:** Design — awaiting review
**Owner:** Vinai
**Builds on:** `2026-06-07-ae-5-improve-existing-design.md` (the existing improvement loop)

## Problem

The article engine improves only the 47 articles it produced. But a read-only
GSC pull (90 days, run during scoping) shows where the search demand actually
is:

| Set | Pages w/ impressions | Clicks | Impressions |
|---|---|---|---|
| **Legacy posts** (untracked by the engine) | 281 | **187** | **660,466** |
| Engine articles (tracked) | 13 | **0** | 487 |

The engine's own content is search-invisible (new / mostly future-scheduled).
**~99.9% of search demand sits on legacy posts the engine cannot currently
see.** "Improve existing articles using traffic data" is therefore a statement
about the **legacy** content — which the engine has no way to ingest, because
`ae-5` requires a local `_draft/04-seo.html` baseline that legacy posts lack.

This project closes that gap: ingest legacy posts into the engine, drive
improvement off real GSC signal, and let Vinai approve changes against a
**rendered** before/after preview.

## Decisions locked (brainstorming 2026-06-09)

- **Target set:** Legacy hand-written WP posts are the priority. Build a
  WordPress importer ("adopt"). The engine's 47 come along for free.
- **Review UX:** Full **rendered side-by-side** visual preview ("how it will
  look and appear"), not just the current text diff.
- **Images:** In scope now (was excluded). Sources: **Pexels** (already wired)
  + **AI-generated diagrams**. Annotated screenshots flagged for manual drop-in.
- **Course dates:** Driven by a post's `course_id` ACF field → the
  `isft/v1/dates` REST endpoint. Rendered via a **client-side widget** (always
  fresh; no baking).
- **Throughput:** 3–4 articles/day (`AE_TOP_K=4`).
- **Autonomy:** Unchanged — nothing auto-publishes; human approval gate stays.
- **Traffic signal:** GSC (clicks/impressions/position/CTR). GA4 not added now.

## Evidence-grounded strategy (5 moves, priority order)

1. **Capture before climb.** Fix titles/meta on pages already ranking pos 1–10
   at ~0% CTR. Cheapest wins on the domain. Examples from the data:
   `how to make a website` (pos 1.0, 1,848 impr, 0% CTR);
   `how to group things together on canva` (pos 1.1, 1,514 impr, 0% CTR).
2. **Climb the striking-distance clusters** (pos 5–20, high impressions, low
   capture): Canva "group" cluster (~3,500 impr), Python "duplicates" cluster
   (already the best-converting blog content — 35 clicks on one post),
   Power BI conditional formatting (1,519 impr).
3. **Interlink legacy ↔ engine.** The engine writes *new* Canva articles while a
   *legacy* Canva post ranks pos 1 for the cluster, and they ignore each other.
   Internal-link selection must span both content sets.
4. **Monetise every improved post** — dated course card + relevant course links
   on each pass (the "upsell with dates" requirement, applied systematically).
5. **Mine gaps into new articles** (feeds the existing `ae-1..ae-8` pipeline) —
   see "New-article opportunities" below.

**Parked (not blog scope):** the WSQ Adobe Photoshop *course page* draws
558,304 impressions ranking ~pos 6 for a competitor's brand (`novasoft
photoshop…`) at 0% CTR. Biggest impression sink on the domain; a course-page
SEO decision for later, noted here so it isn't lost.

## Architecture — the delta nests on the existing engine

An **"adopt" importer** pulls each legacy post into the engine's existing
artifact format (`_draft/04-seo.html` baseline + a `status` entry tagged
`source: legacy`). **After adoption a legacy post is indistinguishable from an
engine article**, so `triage.py`, `ae-5`, the review dashboard, course cards,
and internal-linking all already apply. We extend; we do not fork.

```
WP legacy post ──[NEW: adopt_legacy.py]──► _draft/04-seo.html + status entry (source: legacy)
                                                   │
                          (now a normal engine article)
                                                   ▼
   triage.py ───────► ae-5 improve ───────► _improve/ ──► dashboard review ──► apply/republish
   (+real GSC          (+images,             (+RENDERED                         (existing
    scoring)            +course-date widget)   side-by-side preview)             republish.py)
```

### Component 1 — `scripts/adopt_legacy.py` (NEW)

Enumerate published posts via WP REST and ingest them.

- Source: `GET {wp_api_base}/posts?status=publish&per_page=100&page=N`
  (paginate), `type=post`. Pull `content.rendered`, `title`, `slug`, `link`,
  `id`, `modified`, and the `course_id` ACF value (via REST `acf`/meta if
  exposed; else via the helper plugin).
- Exclude engine-owned posts (slug already in `status/<site>.yaml`, or carries
  `ae_content_uid` meta).
- For each adopted post, write:
  - `content/<site>/<slug>/_draft/04-seo.html` — frontmatter
    (`title`, `url`, `wp_post_id`, `course_id?`, `source: legacy`) + the post
    body HTML as the **baseline ("before")**.
  - A `status/<site>.yaml` entry: `status: published`, `wp_post_id`, `url`,
    `source: legacy`, `adopted: <date>`, `course_id?`; `last_improved` absent.
- Idempotent: skip already-tracked slugs; rerun no-ops.
- **Selection:** default = top legacy blog posts by GSC clicks first (the
  importer can rank against the GSC by-page pull), so we adopt the
  highest-value posts before the long tail. Configurable cap per run.

Reuses `scripts/lib/wp_client.py`. Republish idempotency: on first `apply`, set
`ae_content_uid` on the adopted post (via helper plugin `/ae/v1/meta`) so
`republish.py` round-trips cleanly.

### Component 2 — GSC scoring rework in `scripts/triage.py`

Today every article scores an identical `12.17` (freshness-only) because GSC
signal only attaches to tracked pages and tracked pages have ~0 traffic. Once
legacy posts are tracked with real URLs, `fetch_all_page_queries` maps real GSC
rows to them. Add explicit, tunable signals (weights in
`seo/audit-budgets.yaml` `triage_weights:`):

| Signal | Definition | Surfaces |
|---|---|---|
| `striking_distance` | Σ impressions of pos 5–20 queries for the page | climb candidates |
| `ctr_gap` | pages with pos ≤ 10 queries, impr ≥ threshold, CTR below expected curve | **capture quick-wins** (distinct category) |
| `clicks` | existing clicks (proven demand) | weight real performers |
| (existing) audit / link-gap / freshness | unchanged | |

Output: a differentiated ranking, plus a separate **CTR-capture shortlist**
(cheap title/meta wins) in `triage-<site>-<date>.md`.

### Component 3 — rendered side-by-side preview in `scripts/review_server.py`

Add a rendered view alongside the existing word-level diff (`lib/review.py`):

- Render **before** (`_draft/04-seo.html` body) and **after**
  (`_improve/04-seo.html` body) as styled HTML in two side-by-side sandboxed
  panes, using a neutral article stylesheet that approximates the blog's
  article column ("how it will appear").
- Resolve `ae:img:` (to local image files) and `ae:sibling:` placeholders in a
  **preview/dry-run** path (reuse the resolution logic in
  `scripts/wp_publish.py`) so images and links render.
- Keep the existing highlighted word-diff panel beneath the panes for precise
  change tracking. Approve/Edit/Reject unchanged.

### Component 4 — images in `ae-5` (incremental)

Lift "imagery out of scope." Under the existing `images_max` budget
(`seo/audit-budgets.yaml`):

- **Pexels** via `scripts/fetch_pexels_inline.py` (existing) for hero/section.
- **AI-generated diagrams** for conceptual illustrations. *Build-time
  dependency:* confirm which generator is actually installed before wiring it
  (do not assume the image-gen extension is present); default to the verified
  one. **Guard:** AI images only for conceptual diagrams, never literal
  software-UI depictions (accuracy risk).
- **Annotated screenshots:** engine emits a placeholder + a digest note
  ("screenshot needed: Excel Filter dialog") for manual drop-in — not
  auto-sourced.

### Component 5 — course dates (incremental)

A post's `course_id` ACF value → live upcoming dates.

- **Contract (probed live):**
  `GET https://www.intellisoft.com.sg/wp-json/isft/v1/dates?course_id=<id>&myos_id=6&limit=5`
  — public, no auth, CORS-open. Returns an array of class objects (each has at
  least `date_label` and `reg_url`; source = `trainme_comyos68.classes ⋈
  courses`, future-dated, ascending). Empty array on no match.
- **Host note:** the route is live on `intellisoft.com.sg` but **404s on
  trainingint.com** — the engine calls it **cross-origin** (works today). Option
  (later): deploy the REST route to trainingint for same-origin.
- **Rendering:** no shortcode exists, and dates change often, so render via a
  **client-side widget** — `render_course_card` (in `scripts/lib/blocks.py`)
  emits `<div class="ae-course-card" data-isft-course="<id>" data-myos="6">…`
  plus a one-time JS asset that fetches the endpoint on page load and fills the
  dates. Always fresh; degrades to the plain card (CTA links to the course
  page) if the fetch is empty/fails. `blocks.py` gains an optional `course_id`
  parameter; the no-`course_id` path is unchanged.

### Component 6 — new-article discovery `scripts/discover.py` (incremental)

Mine GSC for demand the site doesn't own:

- Pull site-wide queries; find queries with impressions ≥ threshold whose
  best-ranking owning page is weak (pos > 10) or absent/mismatched.
- Cluster and rank → `status/ideas-<site>.md` + create `idea`-status entries in
  `courses/<site>.yaml` for `ae-1..ae-8`. Surface in the dashboard.

## New-article opportunities (from the GSC pull)

- **Python cluster** — `find duplicates in a python list` is the best blog
  converter; demand spans intro-Python and real-world-projects. Build the
  cluster, link the Python course.
- **Photo-editing / Photoshop** — large impression base (red-eye, restore old
  photos, marquee tool) + course intent (`photoshop course skillsfuture
  singapore`). How-to cluster → Photoshop course upsell.
- **Canva "group" cluster** — improve the legacy post *and* interlink the
  engine's new Canva articles.
- **Web design** — `how to make a website` (pos 1 / 0% CTR) → WordPress /
  web-design course intent.

## Phasing

### Quick wins (immediate, little/no build)
- Set `AE_TOP_K=4` on the nightly task (3–4/day).
- Standing GSC opportunity report (CTR-capture + striking-distance +
  new-article lists) — actionable by hand before any code ships.
- Flag `_tmp_seo_writer.py` (confirmed one-off scratch) for deletion.

### Phase 1 — go-live core
- `adopt_legacy.py` (Component 1).
- GSC scoring rework + CTR-capture shortlist (Component 2).
- Rendered side-by-side preview (Component 3).

### Incremental (one per session after go-live)
- Images in `ae-5` (Component 4).
- Course-date widget (Component 5).
- CTR-capture mode in `ae-5` (title/meta/snippet-only improvements for the
  shortlist; cheap, high ROI).
- New-article discovery (Component 6).
- "For humans" / E-E-A-T pass (TL;DR, last-updated stamp, author bio, FAQ,
  freshened stats).
- Legacy ↔ engine interlinking across both content sets.
- Multi-domain generalisation (`config` is already multi-site-capable).

## Data model changes

Per entry in `status/<site>.yaml`:
- `source: legacy | engine` — provenance (engine entries default `engine`).
- `course_id: <int>` — optional; drives the dates widget.
- `adopted: <ISO date>` — legacy only; set by `adopt_legacy.py`.

`seo/audit-budgets.yaml` `triage_weights:` gains `striking_distance`,
`ctr_gap`, `clicks` weights + a `ctr_gap` impression threshold and expected-CTR
curve.

## Risks / edge cases

- **Legacy HTML round-trip fidelity** — adopting `content.rendered` and later
  republishing must not mangle formatting/shortcodes. Validate on ONE post
  before bulk adoption; the baseline must be byte-faithful enough that an
  unchanged republish is a no-op diff.
- **Live legacy posts are higher-stakes** than scheduled engine drafts (real
  traffic). Improvements must be **additive / first-do-no-harm**; approve and
  republish **one at a time** initially; voice-damage n-gram guard stays.
- **`course_id` ACF on posts** — the field group is currently location-bound to
  the course-page *page* template; confirm it is registered/exposed for
  `post` type (a `post` group exists in `class-acf-fields.php` but must be
  verified) or have the is-coursepage side add a location rule. Dependency, not
  a blocker for Phase 1.
- **Cross-origin dates endpoint** depends on intellisoft.com.sg uptime; widget
  must hide gracefully on empty/error.
- **GSC row sampling** — the site-wide query pull hit the 5,000-row cap;
  for full long-tail coverage, page-filtered or date-partitioned queries may be
  needed in `discover.py`.
- **AI-diagram accuracy** for software UIs — restricted to conceptual diagrams;
  flagged for review.

## Success criteria (Phase 1)

- `adopt_legacy.py` imports the top legacy blog posts by GSC clicks into
  `status` + artifacts; idempotent rerun no-ops.
- `triage.py` ranking is **differentiated** (no longer uniform `12.17`); the
  CTR-capture shortlist surfaces; Canva-group / Python-duplicates posts rank
  high.
- `ae-5` produces a staged improvement on one real legacy post (e.g.
  `how-to-group-on-canva…` or `how-to-find-duplicates-in-a-python-list`); voice
  guard passes; budgets respected.
- The dashboard renders before/after **side by side** faithfully; Approve
  round-trips to the live post via `republish.py`.

## Out of scope (this project)

- GA4 integration (GSC is the traffic signal for now).
- Auto-publishing without review (hard gate stays).
- The Photoshop course-page / competitor-brand-impression question (parked).
- Server-rendered course-date shortcode in the is-coursepage plugin (the
  client-side widget covers it without touching that project).
