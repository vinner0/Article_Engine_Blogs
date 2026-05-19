# Article Engine — Design Spec

**Date:** 2026-05-19
**Owner:** Vinai Prakash
**Status:** Revised post-audit (v2). Independent adversarial audit run 2026-05-19; verdict was REWORK; this version incorporates every BLOCKER/MAJOR finding. Pending owner review.
**Project root:** `D:/VP/ARTICLE_ENGINE/`
**PKM project:** `article-engine`

A registry-driven external engine that turns a per-site course-topic queue into SEO-researched, voice-matched, deeply-linked WordPress articles, pushed daily as **drafts the owner reviews and publishes**. Built for trainingint.com first; architected so every other WordPress property is a config entry, not a rebuild.

> **Honesty note (post-audit).** An earlier draft framed this as "a fusion of two proven systems, ~70% reused." A filesystem audit proved that false: the primary cited source (`D:/VP/BLOG_AUDIT/`) contains **zero code** — it is an approved-but-unbuilt spec. This project is **~70% net-new Python**. What is genuinely reusable is *prompt/stage design* and *reference content data* (voice rules, SEO checklist, link-budget, schema templates, course topology), not executable libraries. Section 3 states the verified reality; all effort/phase/cost reasoning derives from that, not from a reuse fantasy.

---

## 1. Goal

For any registered WordPress site:

1. Take the **courses we sell** as the topic source.
2. Expand each course into a **cluster of ~5 articles**, each from real keyword + SERP research.
3. Generate full articles — research, prose, images, links, SEO meta, schema — that **read like Vinai, not AI slop**.
4. Each article **promotes 1 primary course** + links **2–3 secondary courses** + **2–3 sibling blog posts**, building a topical-authority mesh around each course URL.
5. **Push one new article/day into WordPress as a draft**; owner reviews, lightly edits, publishes.
6. Scale to several WordPress sites with **no code change** — config + topic file + WP credential only.

## 2. Locked decisions

| # | Decision | Choice | Post-audit note |
|---|---|---|---|
| D1 | Run model | External Python engine + WP REST push | **Conditional** — see D1′ |
| D1′ | REST-write contingency | If P0 proves SEO-plugin meta is **not** writable via external REST + app password, a **mandatory thin helper plugin** per site is added. D1's "no plugin" is not guaranteed; it is decided by the P0 probe. | New (audit F2) |
| D2 | Publish autonomy | Auto-generate → WP **draft**; human reviews **and edits** before publish | Strengthened: the human gate is a *genuine edit pass*, not a 1-click rubber stamp — this is the real scaled-content-abuse defence (audit F4) |
| D3 | Content model | Cluster per course (~5) + full keyword/SERP research | unchanged |
| D4 | v1 scope | trainingint.com first; multi-site-ready architecture | unchanged |
| D5 | Build strategy | New standalone project; reuse is **design + content data**, not code | Reframed (audit F1) |

## 3. Reuse reality (filesystem-verified 2026-05-19)

Every row below was checked against the actual filesystem by an independent auditor. "Reuse" means one of: **CODE** (importable/forkable), **DESIGN** (a prompt/spec to re-implement), **DATA** (reference content used as-is).

| Asset spec needs | Claimed source | Verified state | Reuse class | Consequence |
|---|---|---|---|---|
| Multi-site WP push client (`wp_client`) | blog-audit `scripts/lib/wp_client.py` | **Does not exist.** `D:/VP/BLOG_AUDIT/` = README + 1 spec, 0 `.py`. Its README: "no implementation yet" | none → **net-new** | Highest-risk, least-proven layer has no code under it. Treated as net-new + unverified (Section 9, 11). |
| `pexels`, `link_health`, `voice_check`, `sales_block` libs | blog-audit `scripts/lib/` | **Do not exist** as Python. Real Pexels = `softskills/scripts/pexels-fetch.mjs` (Node). Real link-health = `softskills/src/lib/link-health.ts` (TS) | DESIGN only | Port Node/TS logic → Python, or shell out to Node/tsx. Net-new Python either way. |
| `config/sites.yaml` registry | blog-audit `config/sites.yaml` | **No file.** Schema defined only in blog-audit spec prose (lines 63–89); credentials never generated | DESIGN | Schema is a sound copyable design; not a populated artifact. WP app passwords must be created. |
| 8-stage generation pipeline | softskills `.claude/commands/blog-*.md` | **Exist, substantive — but are Claude slash-command prompts**, human-driven, publishing to Astro MDX/git/Coolify | DESIGN | Reusable as *prompt design*. Rebuilding them as an unattended autonomous Python orchestrator targeting WP REST is most of this build. |
| Voice rule files (`voice.md`, `humor.md`, `opinions.md`, `stats.md`, `stories.md`, `do-not-write.md`) | softskills `voice/` | **Exist, real, substantive.** `stats.md` facts locked, already trainingint-centric | **DATA — true reuse** | Used as-is (vendored copy, Section 10). |
| Voice example `corpus/` | softskills `voice/corpus/` | **Empty** — all 4 subdirs `.gitkeep` only | none | No worked-example corpus exists. Voice matching relies on the rule files only; any "match against corpus" idea is unsupported and dropped. |
| SEO checklist / link-budget / schema-templates / pillar-map | softskills `seo/` | **Exist, real, substantive** (checklist = 80 items; pillar-map = real trainingint topology). schema-templates.md says canonical impl is `src/lib/schema/*.ts` | **DATA — true reuse** (rules); schema *generator* is net-new Python | Rules/topology reused directly; JSON-LD builder re-implemented. |
| Daily digest email + AI-provider factory + rate-limit | is-auto-seo `plugin/includes/*.php` | **Exist — PHP plugin classes**, server-side meta via `wp_update_post`/`get_post_meta` | DESIGN | Re-implement as Python. **Critically: proves nothing about external-REST meta writes** (audit F2). |
| "softskills MDX already links to trainingint course URLs" | `…/how-to-communicate-effectively-with-clients/index.mdx` | **True** | DATA point | De-risks **content strategy only** — not WP integration (audit F8). |

**Build baseline:** ~70% net-new Python. Genuine reuse = voice rule files, SEO checklist, link-budget, schema templates, course topology (all DATA), plus stage/prompt designs (DESIGN). No forkable code exists. All downstream phases (Section 14) and cost (Section 13) are derived from this baseline.

## 4. Non-goals

Refreshing existing posts (blog-audit's intended job) · off-page SEO/backlinks · comments/newsletter/multilingual · auto-publishing live with no human edit (D2) · Elementor-built article bodies.

## 5. Architecture

### 5.1 Topology

```
D:/VP/ARTICLE_ENGINE/
├── config/sites.yaml               # registry (schema adapted from blog-audit spec text)
├── courses/trainingint.yaml        # course → cluster → article topic spine (per site)
├── credentials/.env                # WP application passwords (gitignored)
├── voice/                          # VENDORED copy of softskills voice rule files + sync.md
├── seo/                            # checklist.md, link-budget.md, schema-templates.md (DATA reuse)
├── imports/<site>/<YYYY-MM-DD>/    # manual Ubersuggest CSV drops
├── content/<site>/<slug>/
│   ├── _research/  cluster.md, intent.md, serp.md, serp-bodies/   # full top-3 text (audit F4)
│   ├── _draft/     01-skeleton.md, 02-draft.md, 03-voice.md, 04-seo.html
│   ├── _audit/     seo-checklist.md, originality.md, cost.json
│   ├── images/
│   └── final.html
├── state/<site>.sqlite             # queue + state machine + backlink jobs (audit F3/F6)
├── scripts/
│   ├── probe.py                    # P0 preflight (design-gating)
│   ├── plan.py                     # courses.yaml → expand → state
│   ├── run.py                      # daily orchestrator (1 slug, idempotent)
│   └── lib/  wp_client.py · pillar.py · keyword.py · serp.py · draft.py ·
│             voice.py · seo.py · linker.py · pexels.py · link_health.py ·
│             ai_provider.py · digest.py · costguard.py · state.py
└── docs/superpowers/specs/
```

All `lib/` modules are **net-new** (Section 3). Names mirror the blog-audit *design* for familiarity only.

### 5.2 State store (replaces "CSV is sole progress store" — audit F3/F6)

`state/<site>.sqlite` (SQLite — the blog-audit "no SQLite" rule was *its* decision for a human one-shot loop; an unattended daily autonomous loop is a different risk class). Tables:

- `articles(slug PK, status, primary_keyword, course_id, scheduled_date, wp_post_id, content_uid, cost_tokens, cost_usd, updated_at)` — explicit state machine: `idea → planned → researched → drafted → voiced → seo_passed → pushed → published`. `wp_post_id` + `content_uid` written **before** the status flip to `pushed`.
- `backlink_jobs(id PK, from_slug, to_slug, status, attempts, expires_at)` — bounded, expiring (audit F5).
- `runs(id, started_at, finished_at, slug, outcome, tokens, usd)` — observability + cost ledger.

Single-writer guarantee via a per-site lock file; SQLite transactions make stage commits atomic. A run that dies mid-stage leaves a consistent prior state; rerun is safe because every external effect is keyed on `content_uid` (Section 9.2).

### 5.3 Data flow

```
courses/<site>.yaml ─plan.py─> state(status=idea/planned)
run.py (daily, one slug, advances state machine, cost-guarded):
  keyword → serp(+full top-3 bodies) → draft → voice → seo(gates) → push → digest
                                                              │
                            WP REST: search-by-uid → create-or-skip draft
                            wp_post_id+uid recorded BEFORE status=pushed
                                                              │
                            owner: email → wp-admin → EDIT → Publish
```

## 6. Course → cluster topic spine

`courses/trainingint.yaml` = source of truth, one block per course. `plan.py` expands each into ~5 keyword-diverse slugs and **dedupes primary keywords site-wide** (cannibalisation guard).

**Audit F9 fix:** owner-authored slugs are authoritative. AI-proposed expansion slugs are written `status=proposed` and are **excluded from the cannibalisation guarantee and never auto-run** until a human + real keyword data promote them. The dedupe guarantee holds only over human-confirmed, real-keyword-backed slugs.

## 7. Pipeline stages

| # | Stage | Output | Does |
|---|---|---|---|
| 0 | `probe` | `sites.yaml` probe block | **Design-gating preflight, Section 11.** Build does not start on a site until it passes. |
| 1 | `plan` | `state` rows | Expand courses → ~5 slugs, dedupe primary keywords, schedule dates, quarantine AI-proposed slugs |
| 2 | `keyword` | `_research/cluster.md`, `intent.md` | 5–15-term cluster from Ubersuggest CSV; AI-only fallback **explicitly flagged `low-confidence`** and excluded from the cannibalisation guarantee |
| 3 | `serp` | `_research/serp.md` **+ `serp-bodies/{1,2,3}.txt`** | Structural target (word count, H2s, gaps) **and the full extracted body text of top-3** — required input for the F4 n-gram gate |
| 4 | `draft` | `01-skeleton.md` → `02-draft.md` + images | Skeleton then full draft; Pexels hero + inline images |
| 5 | `voice` | `03-voice.md` | Apply Vinai voice rule files; log rules fired; record n-gram baseline of this prose |
| 6 | `seo` | `04-seo.html` + `_audit/*` | 80+ checklist; insert links per budget (Section 8); meta; JSON-LD; **gates defined in Section 7.1** |
| 7 | `push` | live WP draft + `final.html` | Section 9.2 idempotent create; record `wp_post_id`+`uid` pre-flip; queue backlink jobs |
| 8 | `digest` | HTML email | Per-post wp-admin **Edit** deep link + meta preview + token/$ cost line |

### 7.1 Gates — concrete algorithms (audit F4)

The "hard refuse-to-push" list is only real if each gate is a runnable definition with its inputs collected upstream:

- **Originality gate** — refuse unless ≥2 of: (a) a string match against a line in `voice/stories.md`; (b) ≥1 analogy sentence not 8-gram-overlapping any `serp-bodies/*`; (c) ≥1 verbatim figure from `voice/stats.md`; (d) a numbered framework/checklist with no 8-gram overlap to `serp-bodies/*`. Mechanically decidable from collected data.
- **Anti-plagiarism n-gram** — any 8-word shingle shared with `serp-bodies/{1,2,3}.txt` → flagged span must be rewritten before push. (Now runnable because stage 3 persists the bodies.)
- **Voice-damage** — 8-word-shingle similarity of `04-seo.html` prose vs `03-voice.md` ≥ 85%, else refuse to overwrite (SEO pass must not rewrite voice).
- **Link budget** — Section 8; schema-invalid or budget-breach → refuse.
- **Cadence** — > configured per-week cap → refuse.
- **Human-edit reality (D2)** — the digest email states plainly that publishing without editing forfeits the scaled-content-abuse defence; the gate's protection is the *edit*, not the click. The engine cannot enforce this, so the spec names it as an operating discipline, not an automated guarantee.

## 8. Deep-linking mesh (audit F5 rework)

Per-article budget (from softskills `seo/link-budget.md`): 1 primary course (above-fold CTA + bottom CTA + 1 contextual, same URL ≤3×, never same paragraph) · 2–3 secondary courses · 2–3 sibling blog posts · 1–2 authoritative external (`target=_blank rel=noopener`, no `rel=sponsored`). Anti-spam: no identical anchors, ≤40% exact-match anchors, no naked URLs/"click here".

**Steady-state problem the audit found:** the engine pushes *drafts*; the owner may publish late or never; so sibling posts rarely resolve 200 and naive "link only live URLs" means the mesh never densifies and the backlink queue grows forever. **Resolution:**

- At push, `linker.py` links siblings that are **published** (200). Unresolved siblings → `backlink_jobs` with `expires_at` (default 60 days) and capped attempts. Expired jobs are dropped and surfaced in the digest, not retried forever.
- When a sibling is later published, the backlink job does **not** silently edit live content. It generates a **new draft revision** of the earlier post with the link inserted (exact-match, body-preserving) and surfaces it in the digest for the same human approve-and-publish gate. Autonomous modification of live published content is explicitly disallowed (consistent with D2).
- Idempotency: each engine-inserted link carries a hidden marker (`data-ae-link` / HTML comment) so reruns detect and skip already-inserted links instead of double-inserting.
- Links are 200-revalidated at the time the backlink revision is built (a previously-live target may have moved).

## 9. WordPress integration

### 9.1 Transport
WP REST API v2 + application passwords; per-site `wp_api_base` + `app_password_env`. App passwords must be **created** (none exist yet — Section 3).

### 9.2 Idempotent post creation (audit F6)
Before `POST /wp/v2/posts`: generate a deterministic `content_uid` (hash of site+slug); `GET` search posts for an existing post carrying that uid in a registered meta key **or** matching the target slug. If found → update that post (no second post). If not → create, then **immediately** record `wp_post_id`+`content_uid` to `state` *before* any further work or status flip. Orphaned media from a failed prior run (uploaded, post not created) are detected by uid-tagged media titles and cleaned/reused. There is no path where a rerun creates a duplicate post.

### 9.3 SEO-plugin meta — design-gating, not assumed (audit F2)
is-auto-seo writes meta *server-side*; that proves nothing about an **external** client writing it over REST with an application password. Yoast/RankMath meta is frequently `show_in_rest:false` or `auth_callback`-protected. Therefore P0 (Section 11) performs an **authenticated write→read round-trip of the actual SEO-plugin meta field on a throwaway draft on the live site.** Outcomes:

- **Writable via REST** → engine writes plugin-native meta directly. D1 holds.
- **Not writable** → **D1′ triggers**: a mandatory thin helper plugin per site exposes a hardened custom endpoint that sets the meta in-process. This is then on the critical path, not "optional."

JSON-LD is injected as an in-content `<script type="application/ld+json">` block (plugin-independent). **Audit caveat:** Yoast/RankMath emit their own `@graph`; to avoid duplicate/conflicting schema the engine emits **only** the schema types the active plugin does not (FAQPage/Article only if absent) — decided by the P0 probe.

### 9.4 Body format + render proof (audit F10)
Posts ship as clean semantic HTML (headings/lists/tables/figure + the JSON-LD block) as a Gutenberg Custom-HTML/classic block. That trainingint posts use Gutenberg/classic (not Elementor) is an **inference**; P0 pushes a real test HTML draft and fetches the rendered preview to confirm it renders acceptably **before P3 is greenlit**. If post bodies are Elementor/builder-bound, the design branches (helper plugin or templated block) — resolved at P0, not during build.

### 9.5 Scheduler
v1: Windows Task Scheduler, one daily `run.py`. Scale: VPS cron. **Silent-failure alerting:** every run writes a `runs` row; if no successful run in 24h the next `digest` (or a watchdog) emails a FAILURE notice — an unattended job that quietly dies must not be invisible (audit gap).

## 10. Voice & SEO discipline (DATA reuse)

Voice **rule files** vendored into `voice/` with a documented `sync.md` (no symlink — Windows symlink/drift risk on locked `stats.md` facts, audit F11). `do-not-write.md` AI-tell blocklist enforced in stages 5–6. No example `corpus/` exists (Section 3) — voice matching is rule-driven only; the spec makes no claim to corpus-based matching. SEO checklist + link-budget + schema templates used as the canonical rule set; JSON-LD builder is net-new Python validated against `schema-templates.md`.

## 11. P0 preflight — design-gating (`probe.py`)

Build does **not** proceed on a site until all pass, and two of these can **branch the architecture**:

1. Authenticated `GET /wp-json/wp/v2/users/me` — REST + app password works.
2. **Write→read round-trip of the live SEO-plugin meta field on a throwaway draft** → branches D1/D1′ (9.3).
3. Which SEO plugin is active (Yoast/RankMath/none) + whether it emits `@graph` (9.3).
4. **Push a test HTML draft, fetch rendered preview, confirm acceptable render** → branches body-format (9.4).
5. Live category/author IDs, REST media MIME/size limits.
6. Keyword-data path: Ubersuggest CSV present? else `low-confidence` AI-only.

Probe results are written into `sites.yaml`; the throwaway test post + media are deleted.

## 12. Risks & failure modes

| Risk | Mitigation |
|---|---|
| Scaled-content-abuse penalty | D2 mandatory **edit** (not 1-click); cadence cap; originality + n-gram gates with real collected inputs (7.1) |
| Reuse premise wrong (was true!) | Section 3 filesystem-verified; baseline = ~70% net-new |
| WP meta not REST-writable | P0 write-read round-trip; D1′ helper-plugin branch |
| Body HTML renders broken | P0 render round-trip before P3 |
| Duplicate post on rerun | uid search-before-create; id recorded pre-flip (9.2) |
| Queue corruption/concurrency | SQLite + lock + transactional state machine (5.2) |
| Backlink queue unbounded / silent live edits | expiring capped jobs; backlinks become draft revisions for human approval (8) |
| Unbounded LLM spend | Section 13 hard ceilings + abort + cost ledger |
| Silent unattended failure | `runs` ledger + 24h FAILURE email (9.5) |
| Cannibalisation via hallucinated keywords | AI-proposed slugs quarantined, excluded from guarantee (6) |
| Locked-fact drift | vendored voice + sync.md, no symlink (10) |

## 13. Cost — hard ceilings (audit F7; deferral rejected)

A daily × multi-site autonomous LLM loop is an open-ended recurring liability and must be bounded **in the design**:

- **Per-run token ceiling** in `costguard.py`; a run exceeding it aborts and emails before continuing (kills prompt-loop runaways, e.g. iterative-fix loops).
- **Per-site and global monthly USD budget** in `sites.yaml`; on breach the daily run refuses until the next month or a manual override.
- Every run's tokens + USD logged to `runs` and shown in the digest.
- **Order-of-magnitude estimate (to refine with a measured first article, not deferred):** ~6 LLM stages over long-form input/output ≈ low-single-digit USD per article at current Opus pricing; ~3/week/site ≈ low-tens USD/site/month; linear in active sites. If the measured first article diverges >2× from this, the cadence/model choice is revisited before scaling.

## 14. Build phases (re-derived from the true ~70%-net-new baseline)

| Phase | Deliverable | Gate |
|---|---|---|
| **P0** | `probe.py` + populated `sites.yaml`/`courses/trainingint.yaml` + WP app password created | All Section 11 pass; D1 vs D1′ and body-format **decided from live evidence** |
| P1 | `state.py` (SQLite + lock + state machine), `plan.py`, `keyword`, `serp` (incl. `serp-bodies/`) | First slug → reviewable research artifacts; state machine survives a killed run |
| P2 | `draft`, `voice`, `seo` + all Section 7.1 gates runnable | First article passes every hard gate; owner reads it and judges the voice for real |
| P3 | `wp_client` (idempotent create, 9.2), `push`, `linker`, `costguard` | First live WP **draft** on trainingint with correct meta/media/links; rerun creates **no** duplicate; cost logged |
| P4 | `digest` + Task Scheduler + 24h failure alert | One article/day lands as a draft unattended for a week; a forced failure produces an alert |
| P5 | Multi-site proof | One more site added via config + P0 only; first draft lands there |

## 15. Open questions for owner

1. Cadence per site for v1 (softskills used 3/week MWF)?
2. `status=draft` (publish anytime) vs `status=future`+date (auto-live on the day after owner approves the queue)?
3. Per-site vs global monthly USD budget figures (Section 13)?
4. Shared voice rule files across all sites, or per-site overrides from day 1?
5. trainingint blog URL structure / category taxonomy to target.
6. Does the owner accept that D2's penalty protection depends on a *genuine edit pass*, not a 1-click publish (Section 7.1)?

---

*Reuse claims in Section 3 were filesystem-verified by an independent audit on 2026-05-19 (verdict: REWORK on v1; this v2 addresses every BLOCKER/MAJOR). Any future "reuse X" claim must be re-verified against the actual filesystem at the time the implementation plan is written, never inferred from a sibling project's README or status.*
