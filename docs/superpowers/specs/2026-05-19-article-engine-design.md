# Article Engine — Design Spec

**Date:** 2026-05-19
**Owner:** Vinai Prakash
**Status:** Draft for review (pending independent audit)
**Project root:** `D:/VP/ARTICLE_ENGINE/`
**PKM project:** `article-engine`

A registry-driven external engine that turns a per-site course-topic queue into SEO-researched, voice-matched, deeply-linked WordPress articles, pushed daily as **drafts the owner 1-click publishes**. Built for trainingint.com first; architected so every other WordPress property is a config entry, not a rebuild.

---

## 1. Goal

Build a content engine that, for any registered WordPress site:

1. Takes the **courses we sell** as the topic source.
2. Expands each course into a **cluster of ~5 articles**, each built from real keyword + SERP research.
3. Generates full articles — research, prose, images, internal/external links, SEO meta, schema — that **read like Vinai, not AI slop**.
4. Makes each article **promote 1 primary course** (CTA + contextual links), link **2–3 secondary courses** and **2–3 sibling blog posts**, building a topical-authority mesh around each course URL.
5. **Pushes one new article per day into WordPress as a draft/scheduled post**; the owner reviews and publishes with one click.
6. Scales to several WordPress sites with **no code change** — only config + a topic file + a WP credential.

This is not greenfield. It fuses two proven PKM systems (Section 3).

## 2. Locked decisions (from 2026-05-19 brainstorm)

| # | Decision | Choice |
|---|---|---|
| D1 | Run model | **External Python engine + WP REST push** (not a per-site PHP plugin) |
| D2 | Publish autonomy | **Auto-generate → WP draft; human 1-click publish** (protects against scaled-content-abuse penalty) |
| D3 | Content model | **Cluster per course (~5 articles) + full keyword/SERP research** |
| D4 | v1 scope | **trainingint.com first; multi-site-ready architecture** |
| D5 | Build strategy | **New standalone project reusing blog-audit + softskills as shared libraries** (Approach A — clean seams; net-new generation kept separate from blog-audit's "refresh existing" lifecycle) |

## 3. Prior art in PKM (reuse map)

Most hard problems are already solved and battle-tested. The engine is a **fusion**, not an invention.

| Layer | Source project | Path | Reuse | Adaptation needed |
|---|---|---|---|---|
| Multi-site registry + WP push | **blog-audit** | `D:/VP/BLOG_AUDIT/` | `config/sites.yaml` schema, `lib/wp_client.py`, `lib/pexels.py`, `lib/link_health.py`, `lib/voice_check.py`, `lib/sales_block.py` | `wp_client` currently writes **draft revisions of existing posts**; must add **create-new-post**, set category/tags, upload featured media, write SEO-plugin meta + JSON-LD |
| 8-stage generation brain | **softskills-sg** | `D:/vp/softskills/1-NEW-SSKILLS/` | The `/blog-*` stage logic: keyword-research → serp-analyze → draft → voice-pass → seo-pass → publish; per-post `_research/_draft/_audit/` artifact discipline; idempotent stages | Output target changes from **MDX** to **WordPress HTML**; publish target changes from git/Coolify to WP REST |
| Voice + originality | softskills-sg | `…/voice/` (`voice.md`, `humor.md`, `opinions.md`, `stats.md`, `stories.md`, `do-not-write.md`, `corpus/`) | Near-verbatim. `stats.md` facts are locked & already trainingint-centric (27 WSQ courses, 48,000+ trained, etc.) | Shared corpus; per-site overrides optional later |
| SEO discipline | softskills-sg | `…/seo/checklist.md`, `seo/link-budget.md`, `seo/schema-templates.md`, `seo/pillar-map.yaml` | 80+ on-page checklist, anti-spam link budget, Article/FAQPage/BreadcrumbList JSON-LD, course→cluster topology | `pillar-map.yaml` → per-site `courses/<site>.yaml` |
| Daily digest email | **is-auto-seo** | `D:/VP/auto-seo/plugin/includes/` (reporter) | HTML email pattern + WP-admin deep links | Reframed: "1 draft ready → Review & Publish" |
| AI provider pattern | is-auto-seo v1/v2 | same | Claude/OpenAI factory; 1s rate-limit discipline | Reused for the generation calls |

**Key fact discovered during research:** softskills.sg blog articles **already point `courseLinks.primary` at trainingint.com course URLs** (verified in `…/src/content/blog/how-to-communicate-effectively-with-clients/index.mdx` frontmatter). The course→article→course relationship this engine automates is the exact pattern softskills already runs manually.

## 4. Non-goals (deferred)

- Refreshing/auditing **existing** posts — that is blog-audit's job; this engine only generates net-new.
- Off-page SEO / backlinks.
- Comments, newsletter, multilingual.
- Auto-publishing **live** with no human review (explicitly rejected, D2).
- A WordPress plugin (explicitly rejected, D1) — except an optional thin read-only helper if REST gaps appear (Section 9.5).
- Elementor-built article bodies — posts ship as portable HTML (Section 9.4).

## 5. Architecture

### 5.1 Topology

```
D:/VP/ARTICLE_ENGINE/
├── README.md                       # PKM-format, path: field
├── config/
│   └── sites.yaml                  # registry (extends blog-audit's schema)
├── courses/
│   └── trainingint.yaml            # course → cluster → article topic spine (per site)
├── credentials/
│   └── .env                        # WP application passwords (gitignored)
├── voice/                          # symlink or synced copy of softskills voice corpus
├── seo/
│   ├── checklist.md                # 80+ on-page items (from softskills)
│   ├── link-budget.md              # anti-spam rules (from softskills)
│   └── schema-templates.md         # JSON-LD (from softskills)
├── imports/<site>/<YYYY-MM-DD>/
│   └── ubersuggest-*.csv           # manual keyword-data drops
├── content/<site>/<slug>/
│   ├── _research/  cluster.md, intent.md, serp.md
│   ├── _draft/     01-skeleton.md, 02-draft.md, 03-voice.md, 04-seo.html
│   ├── _audit/     seo-checklist.md, originality.md
│   ├── images/     pexels-fetched, optimised
│   └── final.html  # frozen at push time
├── queue/<site>.csv                # per-slug status + scheduled date (sole progress store)
├── scripts/
│   ├── plan.py                     # course.yaml → expand clusters → fill queue
│   ├── run.py                      # daily orchestrator: next slug → stages → email
│   └── lib/
│       ├── wp_client.py            # forked+extended from blog-audit
│       ├── pillar.py               # cluster expansion + primary-keyword dedupe
│       ├── keyword.py              # Ubersuggest CSV → cluster/intent (AI fallback)
│       ├── serp.py                 # top-3 structural analysis
│       ├── draft.py                # skeleton→draft, Pexels images
│       ├── voice.py                # voice pass + voice-damage n-gram check
│       ├── seo.py                  # checklist, link budget, schema, originality
│       ├── linker.py               # resolve internal links to live URLs + back-link queue
│       ├── pexels.py               # from blog-audit
│       ├── link_health.py          # from blog-audit
│       └── digest.py               # daily email (is-auto-seo pattern)
└── docs/superpowers/specs/         # this spec
```

3 entry points (`plan.py`, `run.py`, plus `wp_client` smoke test), ~11 lib modules — most ported, not new.

### 5.2 Data flow

```
courses/<site>.yaml ──plan.py──> queue/<site>.csv (status=idea)
                                        │
run.py (daily, one slug, status=idea→…→pushed):
  keyword ─> serp ─> draft ─> voice ─> seo ─> push ─> digest email
                                                 │
                                    WP REST: media upload + create post
                                    status=draft (or future+date)
                                                 │
                                    queue row → pushed; back-link jobs queued
                                                 │
                              Owner opens wp-admin link in email → Publish
```

Every stage writes its artifact before declaring success; reruns are safe (softskills atomicity principle).

## 6. Course → cluster topic spine

`courses/trainingint.yaml` is the source of truth. One block per course; `plan.py` expands each into ~5 keyword-diverse article slugs and dedupes primary keywords across the whole site (no two articles target the same primary keyword — the cannibalisation guard softskills enforces).

```yaml
site: trainingint
courses:
  - id: writing-professional-emails
    course_url: https://www.trainingint.com/writing-professional-emails
    pillar: communication
    cluster:
      - slug: how-to-write-a-professional-email
        primary_keyword: how to write a professional email
      - slug: how-to-write-a-follow-up-email
        primary_keyword: how to write a follow up email
      # … ~5 total; secondary courses inferred from same pillar
    secondary_courses:                       # the 2–3 cross-links
      - https://www.trainingint.com/communicate-with-confidence
      - https://www.trainingint.com/business-presentation-skills-training-singapore
```

`plan.py` may **propose** additional cluster slugs (AI keyword expansion) for owner approval rather than inventing them silently — keeps a human in topic selection.

## 7. Pipeline stages

| # | Stage | Input | Output | Does |
|---|---|---|---|---|
| 0 | `plan` | `courses/<site>.yaml` | `queue/<site>.csv` | Expand each course → ~5 slugs, dedupe primary keywords, set status=idea, assign cadence dates |
| 1 | `keyword` | primary kw + `imports/<site>/…/ubersuggest-*.csv` | `_research/cluster.md`, `intent.md` | Build 5–15-term cluster (KD/volume filtered); classify intent; flag if blog is wrong format. **AI-only fallback** if no CSV, written with a `low-confidence-keywords` flag in the artifact |
| 2 | `serp` | primary kw | `_research/serp.md` | Top-3 ranking pages (exclude Reddit/Quora/YT): avg word count, H2 set, format, **coverage gaps** = the structural target |
| 3 | `draft` | cluster+serp+voice | `_draft/01-skeleton.md` → `02-draft.md` + `images/` | Skeleton (H1/H2/FAQ/CTA/image slots), then full draft; Pexels hero + inline images |
| 4 | `voice` | `02-draft.md` + `voice/*` | `_draft/03-voice.md` | Apply Vinai voice/humour/opinions/stats/stories; log which rules fired |
| 5 | `seo` | `03-voice.md` + checklist + link-budget | `_draft/04-seo.html` + `_audit/seo-checklist.md`, `originality.md` | 80+ checklist; insert links per budget (Section 8); meta title/desc; JSON-LD; **originality gate** (≥2 of story/analogy/stat/framework); **n-gram anti-plagiarism** vs top-3; **voice-damage check** refuses to overwrite if prose drifted from stage 4 |
| 6 | `push` | `04-seo.html` | live WP draft + `final.html` | WP REST: upload featured+inline media; create post `status=draft` (or `future`+date); set category/tags; write Yoast **or** RankMath meta + JSON-LD; resolve internal links to **live** URLs; queue back-link jobs; queue row → pushed |
| 7 | `digest` | day's pushed slugs | HTML email | "N draft(s) ready" + per-post wp-admin **Edit** deep link + title/meta preview |

Hard refuse-to-push conditions (ported from softskills, all enforced before stage 6 writes anything): >3 primary-course links · 0 internal sibling links · 0 authoritative outbound · cadence cap exceeded · originality gate failed · n-gram overlap with a top-3 result · schema invalid.

## 8. Deep-linking mesh (core requirement)

Per-article link budget (from softskills `seo/link-budget.md`, anti-spam-disciplined):

| Target | Count | Placement |
|---|---|---|
| **Primary course** | 1 URL | CTA above fold + CTA bottom + 1 contextual body link (same URL ≤3×, never same paragraph) |
| **Secondary courses** | 2–3 | Contextual body links, descriptive anchors |
| **Sibling blog posts** (same cluster/pillar) | 2–3 | Contextual; **resolved at push time against posts that are actually live** on the site |
| **Authoritative external** | 1–2 | SSG/MOM/HBR/peer-reviewed; `target=_blank rel=noopener`, no `rel=sponsored` |

Anti-spam discipline (verbatim from softskills): no identical anchors; ≤40% exact-match anchors; no naked URLs / "click here"; one primary CTA above fold + one bottom; refuse-to-publish if budget breached.

**404-avoidance (lesson from softskills):** softskills shipped sitewide `courseLinks.primary` 404s by linking pages that did not yet exist. The engine's `linker.py` queries the target site's WP REST for live posts/pages and only emits internal links that resolve **200**; unresolved sibling links are deferred to a **back-link queue**.

**Back-link mesh tightening:** when a newer cluster sibling goes live, queued jobs add a link to it from earlier published siblings (via WP REST post update, preserving body, exact-match insert only — blog-audit's content-safety pattern). The topical mesh densifies automatically without re-running generation.

## 9. WordPress integration

### 9.1 Transport
WP REST API v2 + **application passwords**, per-site base URL + credential env var (blog-audit's `sites.yaml` already defines `wp_api_base` + `app_password_env` for trainingint, intellisoft, vinaiprakash, excelchamp).

### 9.2 Post creation
`POST /wp/v2/posts` with `status=draft` (D2) or `status=future` + `date` for scheduled drip. Set `categories`, `tags`, `author`, `featured_media` (from a prior `POST /wp/v2/media` upload of the optimised Pexels hero).

### 9.3 SEO-plugin meta
Yoast and RankMath expose meta differently over REST. The engine **detects the installed plugin per site** (probe REST schema / known meta keys) and writes the matching fields (`_yoast_wpseo_title`/`_yoast_wpseo_metadesc` vs RankMath `rank_math_title`/`rank_math_description`). JSON-LD is injected into post content as a `<script type="application/ld+json">` block so it is plugin-independent. **Unverified — see Section 11.**

### 9.4 Body format
Posts ship as clean semantic HTML (headings, lists, tables, figure/img, the JSON-LD block) that renders correctly in Gutenberg (as a Custom HTML block or classic content) and the classic editor. **No Elementor** — Elementor is trainingint's page builder; blog posts use the standard editor (assumption, Section 11).

### 9.5 Optional thin helper plugin
Only if REST gaps surface (e.g. app passwords blocked, or meta not writable): a minimal read-only/receiver plugin per site. Deferred; not in v1 unless audit/probe forces it.

### 9.6 Scheduler
v1: Windows Task Scheduler on Vinai's machine — one daily `run.py` invocation (pick next queued slug → stages 1–7). Scale path: VPS cron. Idempotent stages mean a missed/failed run is safe to rerun.

## 10. Voice & SEO discipline (ported, proven)

- **Voice corpus** reused from softskills `voice/`; `stats.md` facts are locked, never paraphrased, already trainingint-centric.
- **`do-not-write.md`** AI-tell blocklist enforced in voice + seo stages ("delve", "in today's fast-paced world", em-dash overuse, etc.).
- **Originality gate**: each article must contain ≥2 of {Vinai story, original analogy not in top-3, locked stat, original framework}. Plus 8-word n-gram overlap check vs top-3 SERP → rewrite flagged phrases.
- **80+ item SEO checklist** produces a per-post pass/fail `seo-checklist.md`.
- **Schema**: Article + FAQPage (from FAQ frontmatter, wins PAA) + BreadcrumbList. No Course schema on posts (wrong-schema-on-wrong-page penalty).

## 11. Assumptions to verify before build (NOT confirmed)

Per the principle that a design doc states intent, not shipped reality — these must be probed against the live site, not assumed:

1. **WP REST + application passwords enabled on trainingint.com.** Security plugins / host hardening frequently disable both. Probe: authenticated `GET /wp-json/wp/v2/users/me`.
2. **Which SEO plugin is installed on trainingint** (Yoast vs RankMath vs none). is-auto-seo's notes say Yoast "may not be installed on production" — so this is genuinely open. Probe REST + active-plugins.
3. **Blog post editor** — confirmed only that Elementor builds *pages*; that posts use Gutenberg/classic is an inference. Verify on a real published post's REST payload.
4. **No keyword API** exists in PKM. Default = manual Ubersuggest CSV drop (softskills' proven method). AI-only path is explicitly lower-confidence and flagged in artifacts.
5. **Category/author IDs** on trainingint for blog posts — must be read from the live site, not guessed.
6. **REST media upload limits / MIME rules** on the host.

`plan.py` build phase 0 is a **`probe.py` preflight** that resolves 1–3, 5, 6 against the live site and writes findings into `sites.yaml`; build does not proceed on a site until preflight passes.

## 12. Risks & failure modes

| Risk | Mitigation |
|---|---|
| Google scaled-content-abuse penalty | Human publish gate (D2); weekly cadence cap (hard refuse); originality + n-gram gates; voice pass |
| AI slop | Voice pass is its own stage; voice-damage n-gram check vs pre-SEO draft |
| Internal-link 404s (softskills got bitten) | `linker.py` resolves only live URLs; back-link queue for not-yet-live siblings |
| SEO-pass nukes voice | Voice-damage check refuses overwrite if prose drifted |
| Keyword cannibalisation | Site-wide primary-keyword dedupe in `plan.py` |
| WP REST blocked / app password off | Preflight probe (Section 11) gates build; thin helper plugin as fallback (9.5) |
| Wrong SEO-plugin meta written | Per-site plugin detection; JSON-LD is plugin-independent |
| Silent push partial-failure | Atomic stages; hard gates abort with explicit errors (blog-audit "no partial state" principle) |
| Cost overrun | Per-article token budget tracked; cadence cap bounds spend (Section 13) |

## 13. Cost model (rough, to refine in plan)

Per article ≈ 6 LLM-bearing stages (keyword, serp, draft, voice, seo, + planning share). Order-of-magnitude estimate to be quantified in the implementation plan with a real token measurement on the first article (no guessing committed to spec). Cadence cap (e.g. 3/week/site) bounds monthly spend; multi-site spend = linear in active sites.

## 14. Build phases

| Phase | Deliverable | Gate |
|---|---|---|
| P0 | `probe.py` preflight + `sites.yaml`/`courses/trainingint.yaml` populated | All Section 11 items resolved for trainingint |
| P1 | `plan.py` → queue; `keyword`+`serp`+`draft` stages | First slug produces a reviewable draft artifact |
| P2 | `voice`+`seo` stages + gates | First article passes all hard gates + owner reads it, judges voice |
| P3 | `wp_client` extend + `push` + `linker` | First live WP **draft** on trainingint with correct meta/media/links, owner 1-click publishes |
| P4 | `digest` email + Task Scheduler | One article/day lands as draft unattended for a week |
| P5 | Multi-site proof | Add one more site via config only; first draft lands there |

## 15. Open questions for audit / owner

1. Cadence per site for v1 (softskills used MWF / 3-per-week)?
2. Shared voice corpus across all sites, or per-site voice from day 1?
3. `status=draft` (manual publish anytime) vs `status=future`+date (auto-goes-live on the scheduled day after the owner approves the queue) — which "1-click" model?
4. Does `plan.py` auto-expand clusters with AI, or only from owner-listed slugs in `courses/<site>.yaml`?
5. trainingint blog URL structure / category taxonomy to target.

---

*This spec fuses `D:/VP/BLOG_AUDIT/docs/superpowers/specs/2026-05-01-blog-audit-foundation-design.md` (multi-site WP push) and `D:/vp/softskills/1-NEW-SSKILLS/docs/superpowers/specs/2026-04-30-softskills-blog-seo-pipeline-design.md` (8-stage generation). Reuse claims in Section 3 are to be verified against actual source files during the implementation plan, not taken on faith.*
