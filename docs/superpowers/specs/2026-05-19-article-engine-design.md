# Article Engine — Design Spec (v3)

**Date:** 2026-05-19
**Owner:** Vinai Prakash
**Status:** v3 — model reversed to **softskills-style human-driven Claude Code batch → WordPress scheduled posts** (owner directive 2026-05-19, supersedes the autonomous-engine model in v1/v2). Independent audit (v1→REWORK) findings that survive the pivot are retained and flagged; findings specific to the autonomous model are deliberately dropped. Pending owner review.
**Project root:** `D:/VP/ARTICLE_ENGINE/`
**PKM project:** `article-engine`

A Claude Code slash-command pipeline — modelled directly on the **proven softskills.sg `blog-1…8` workflow** — that the owner runs in **batches of 5–15 articles**, reviews, and then pipelines into WordPress as **future-dated scheduled posts** which WordPress publishes itself on schedule. trainingint.com first; multi-site = config + a topic file, not a rebuild.

> **Why v3.** v1 assumed a reuse fantasy (audit-corrected). v2 hardened a fully autonomous unattended engine. The owner has chosen the **softskills execution model**: human babysits Claude Code in batches, reviews, then schedules. This is simpler, lower-risk, and reuses softskills' proven *workflow*, not just its prompt text. The autonomous-engine machinery (daemon, SQLite state, OpenAI API + cost ceilings, idempotent-cron guards, failure alerting) is deliberately removed — it solved problems this model does not have. The WordPress publish stage and its preflight probe remain net-new and are the real engineering and the real risk.

---

## 1. Goal

For any registered WordPress site:

1. Take the **courses we sell** as the topic source; expand each into a **cluster of ~5 articles**.
2. Owner runs the pipeline in **batches of 5–15 articles** in Claude Code, with research, drafting, voice, SEO, and a **human review gate** at the same point softskills gates (post voice-pass).
3. Each article **promotes 1 primary course** + **2–3 secondary courses** + **2–3 sibling blog posts** + 1–2 authoritative external links (topical-authority mesh around the course URL).
4. After review, the batch is **pushed to WordPress as scheduled (`status=future`) posts on a 5/week-weekday cadence**; WordPress publishes them automatically on their dates.
5. Reads like Vinai, not AI slop (softskills voice rules + originality gate).
6. Scales to other WordPress sites with **no code change** — a `sites.yaml` entry + a `courses/<site>.yaml` + a WP application password.

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Execution model | **Human-driven Claude Code slash-command pipeline, run in batches** (softskills model). Not an unattended engine. |
| D2 | Generation | Claude Code itself (the agent + sub-agents), as softskills did. **No programmatic LLM API, no API key, no cost ceiling** — cost is bundled Claude Code usage. |
| D3 | Review gate | Mandatory human review after the voice pass (softskills Stage 5 gate), then a second look at the assembled batch before push. Owner explicitly babysits. |
| D4 | Publish mechanism | Push reviewed batch via WP REST as **`status=future` + scheduled `date`**, 5/week weekdays; **WordPress's own scheduler publishes them**. No external scheduler/daemon. |
| D5 | Content model | Cluster per course (~5) + full keyword/SERP research (softskills `pillar-map` topology). |
| D6 | v1 scope | trainingint.com first; multi-site-ready by config. |
| D7 | Build strategy | New project; reuse softskills' **workflow design + content DATA**; only the WP-publish helper is net-new code. |
| — | *Reversed from v2* | OpenAI/`ai_provider.py`, SQLite state machine, `costguard`, 24h failure alerts, unattended scheduler — **all dropped** (not needed in the human-batch model). |

## 3. Reuse reality (filesystem-verified 2026-05-19; honest after the v1 audit)

| Asset needed | Source | Verified | Reuse class | Note |
|---|---|---|---|---|
| 8-stage pipeline **workflow + prompts** | softskills `.claude/commands/blog-1…8.md` | Exist, substantive, **same human-driven Claude Code execution model we are now adopting** | **DESIGN — now directly reusable as a workflow**, not just text (the v1/v2 caveat was for the autonomous model; in the batch model the model matches) | Adapt outputs: WordPress HTML instead of Astro MDX; Stage 8 pushes WP scheduled post instead of MDX→git→Coolify |
| Voice rule files (`voice.md`, `humor.md`, `opinions.md`, `stats.md`, `stories.md`, `do-not-write.md`) | softskills `voice/` | Exist, real; `stats.md` locked & trainingint-centric | **DATA — true reuse** | Vendored copy + `sync.md` (no symlink — drift risk on locked facts) |
| Voice example `corpus/` | softskills `voice/corpus/` | **Empty** (`.gitkeep` only) | none | No corpus-based matching is claimed; voice = rule files only |
| SEO checklist (80 items), link-budget, schema-templates, pillar-map | softskills `seo/` | Exist, real, trainingint topology already present | **DATA — true reuse** | JSON-LD *builder* is net-new (small) |
| WP publish helper (REST: scheduled post, media, meta, schema, links) | blog-audit `scripts/lib/wp_client.py` | **Does not exist** — `D:/VP/BLOG_AUDIT/` is README+spec, 0 `.py` | none → **net-new** | The only substantial net-new code; the real engineering + the audit's surviving risk (Section 8) |
| `sites.yaml` registry schema | blog-audit spec prose | Design only, no file/credentials | DESIGN | Copyable schema; WP app passwords must be created |
| softskills MDX already links to trainingint course URLs | `…/index.mdx` frontmatter | True | DATA point | De-risks content strategy only |

**Build baseline:** small. Genuine reuse = the softskills *workflow* (DESIGN, model now matches) + voice/SEO/topology DATA. **Net-new code = the WordPress publish helper + a JSON-LD builder.** Everything else is prompts and reference data.

### 3.1 Execution model is now the softskills model (no longer a category mismatch)

softskills' generators are Claude-Code slash-command prompts run interactively by a human in batches with sub-agents (verified: `blog-3-draft.md` is a prompt with "wait for their go-ahead"; only `PEXELS_API_KEY` in its `.env`). v1/v2 flagged this as non-reusable *because v1/v2 wanted an unattended daemon*. v3 adopts the same human-batch model, so the workflow **is** the reuse. The single divergence: softskills Stage 8 wrote MDX to git and Coolify rebuilt Astro; here Stage 8 calls WP REST to create a future-dated post and WordPress's scheduler publishes it. That divergence is the net-new helper (Section 7 stage 8, Section 8).

## 4. Non-goals

Unattended/daemon operation · programmatic LLM API · refreshing existing posts (blog-audit's job) · off-page SEO · comments/newsletter/multilingual · Elementor-built article bodies.

## 5. Architecture

### 5.1 Topology

```
D:/VP/ARTICLE_ENGINE/
├── .claude/commands/               # the pipeline — modelled on softskills blog-1…8
│   ├── ae-1-keyword-research.md
│   ├── ae-2-serp-analyze.md
│   ├── ae-3-draft.md               # skeleton→draft, Pexels images
│   ├── ae-4-voice-pass.md
│   ├── ae-6-seo-pass.md            # 80+ checklist, links, schema, originality+n-gram gates
│   ├── ae-8-publish.md             # batch → WP scheduled posts (calls the helper)
│   └── ae-batch.md                 # drive 5–15 slugs through 1→6, stop at review gate
├── config/sites.yaml               # registry (schema from blog-audit spec text)
├── courses/trainingint.yaml        # course → cluster → article topic spine
├── credentials/.env                # WP application passwords + PEXELS_API_KEY (gitignored)
├── voice/                          # vendored softskills voice rule files + sync.md
├── seo/                            # checklist.md, link-budget.md, schema-templates.md (DATA)
├── imports/<site>/<YYYY-MM-DD>/    # manual Ubersuggest CSV drops
├── content/<site>/<slug>/
│   ├── _research/  cluster.md, intent.md, serp.md, serp-bodies/{1,2,3}.txt
│   ├── _draft/     01-skeleton.md, 02-draft.md, 03-voice.md, 04-seo.html
│   ├── _audit/     seo-checklist.md, originality.md
│   ├── images/
│   └── final.html
├── status/<site>.yaml              # batch status map (like softskills pillar-map: slug→status+scheduled_date)
├── scripts/
│   ├── probe.py                    # P0 preflight (design-gating, Section 9)
│   └── wp_publish.py               # net-new WP REST helper (scheduled post, media, meta, schema, links)
└── docs/superpowers/specs/
```

Only `probe.py` and `wp_publish.py` are code. The pipeline is slash-command prompts; the owner runs them.

### 5.2 Batch flow

```
courses/<site>.yaml ──(owner + /ae-1)──> pick 5–15 slugs, cluster, dedupe primary keywords
  /ae-batch:  per slug → ae-1 keyword → ae-2 serp(+top-3 bodies) → ae-3 draft+images
                       → ae-4 voice ──🛑 OWNER REVIEW (read, edit, accept)──> ae-6 seo+gates
  owner reviews the assembled batch (titles, links, schedule dates)
  /ae-8-publish <batch>:  for each accepted slug →
        wp_publish.py: upload media → create post status=future, date=scheduled_day
                       → set category/tags/author → write SEO-plugin meta + JSON-LD
                       → resolve internal links to in-batch/published URLs
                       → status/<site>.yaml: slug → scheduled
  WordPress's own scheduler publishes each post on its date. No daemon here.
```

State is per-article files + `status/<site>.yaml` — exactly the softskills artifact discipline. Reruns are safe because each stage rewrites its own artifact and the publish helper is idempotent (Section 8).

## 6. Course → cluster topic spine

`courses/trainingint.yaml`, one block per course; `/ae-1` (with owner) expands each into ~5 keyword-diverse slugs and **dedupes primary keywords site-wide** (cannibalisation guard, from softskills `pillar-map` rule "primary keywords MUST be unique"). AI-proposed extra slugs are written `status: proposed` and **not run** until the owner promotes them — keeps a human in topic selection.

## 7. Pipeline (slash commands, softskills-modelled)

| Cmd | Output | Does |
|---|---|---|
| `/ae-1-keyword-research <slug>` | `_research/cluster.md`, `intent.md` | 5–15-term cluster from Ubersuggest CSV; AI-only fallback explicitly flagged `low-confidence` |
| `/ae-2-serp-analyze <slug>` | `_research/serp.md` + `serp-bodies/{1,2,3}.txt` | Top-3 structural target **and full body text** (input for the originality/n-gram gates) |
| `/ae-3-draft <slug>` | `01-skeleton.md` → `02-draft.md` + `images/` | Skeleton (owner go-ahead) → full draft; Pexels hero+inline (PEXELS_API_KEY, as softskills) |
| `/ae-4-voice-pass <slug>` | `03-voice.md` | Apply Vinai voice rule files; log rules fired |
| **🛑 OWNER REVIEW** | edited `03-voice.md` | Owner reads, edits, accepts — the real scaled-content-abuse defence (genuinely satisfied, D3) |
| `/ae-6-seo-pass <slug>` | `04-seo.html` + `_audit/*` | 80+ checklist; insert links per budget (Section 8); meta; JSON-LD; **originality gate** (≥2 of story/analogy/stat/framework, mechanically checked vs `serp-bodies/`); **8-word n-gram anti-plagiarism vs `serp-bodies/`**; **voice-damage check** (refuse if prose drifted from `03-voice.md`) |
| `/ae-batch <n>` | drives the above for a batch, stops at review gate | Lets owner push 5–15 through research→seo, then review together |
| `/ae-8-publish <batch>` | live WP **scheduled** posts + `status/<site>.yaml` | Calls `wp_publish.py` per accepted slug (Section 8). Refuse-to-publish gates from softskills enforced before any WP write: link-budget breach, 0 internal links, 0 authoritative outbound, originality fail, n-gram overlap, schema invalid. |

## 8. WordPress publish helper (`wp_publish.py`) — the net-new code + surviving audit risk

The only substantial engineering. Per accepted slug:

1. **Idempotent create:** deterministic `content_uid` (hash site+slug) stored in a post meta key; before create, search WP for that uid (or the slug) → update if found, else create. A rerun of `/ae-8` never makes a duplicate post. `wp_post_id` recorded to `status/<site>.yaml` immediately after create.
2. **Media:** upload optimised Pexels hero + inline images via `POST /wp/v2/media`; set `featured_media`.
3. **Scheduled post:** `POST /wp/v2/posts` with `status=future`, `date` = the slug's weekday slot; set `categories`, `tags`, `author`.
4. **SEO meta + schema (audit F2 — STILL DESIGN-GATING):** write the active SEO plugin's meta. **is-auto-seo writing meta server-side proves nothing about an external REST client writing it with an application password.** Yoast/RankMath meta is often `show_in_rest:false`. Resolved by P0 (Section 9): if not REST-writable → a **mandatory thin helper plugin** per site exposes a hardened endpoint (D1's "no plugin" is then void for that site). JSON-LD injected as an in-content `<script type="application/ld+json">`; emit **only** schema types the active plugin does not, to avoid duplicate `@graph` (decided by P0).
5. **Internal links (softskills 404 lesson):** softskills shipped sitewide 404s by linking pages that didn't exist. In the batch model siblings are created together, so `wp_publish.py` resolves intra-batch links to the scheduled siblings' WP URLs and only emits external-to-batch internal links that resolve 200 on the live site. No silent edits to already-published posts; if a later batch should back-link an earlier post, that is done as a **new WP draft revision for owner approval**, never an autonomous live edit.
6. **Body HTML (audit F10):** clean semantic HTML + JSON-LD as a Gutenberg Custom-HTML/classic block. That trainingint posts are Gutenberg/classic (not Elementor) is verified by P0's render round-trip before any real batch.

## 9. P0 preflight — design-gating (`probe.py`, run once per site)

No batch is published to a site until these pass; two can branch the design:

1. Authenticated `GET /wp-json/wp/v2/users/me` — REST + app password works.
2. **Write→read round-trip of the live SEO-plugin meta field on a throwaway draft** → decides REST-write vs mandatory helper plugin (Section 8.4).
3. Active SEO plugin (Yoast/RankMath/none) + whether it emits its own `@graph`.
4. **Push a test HTML draft, fetch rendered preview, confirm it renders acceptably** → decides body-format (Section 8.6).
5. Live category/author IDs; REST media MIME/size limits.
6. **WordPress scheduled-post reliability (new, from is-auto-seo PKM note):** confirm a real server cron hits `wp-cron.php` (or install a missed-schedule guard). Native wp-cron fires only on traffic; a future-dated post on a quiet day can "miss schedule." This is the one operational gotcha of the WP-native-scheduler choice (D4) and must be resolved before relying on automatic daily appearance.
7. Keyword-data path: Ubersuggest CSV present? else `low-confidence` AI-only.

Probe results written into `sites.yaml`; the throwaway post/media deleted.

## 10. Voice & SEO discipline (DATA reuse)

Voice **rule files** vendored into `voice/` with a documented `sync.md` (no symlink — Windows drift risk on locked `stats.md` facts). `do-not-write.md` AI-tell blocklist enforced in `/ae-4` and `/ae-6`. No example corpus exists (Section 3) — voice is rule-driven only. SEO checklist + link-budget + schema templates used as the canonical rule set; JSON-LD builder (small, net-new) validated against `schema-templates.md`. Originality + n-gram gates are mechanically decidable because `/ae-2` persists `serp-bodies/`.

## 11. Risks (post-pivot)

| Risk | Mitigation |
|---|---|
| Scaled-content-abuse penalty | Owner genuinely babysits + reviews + edits (D3) — the audit's stated only-real defence, now actually met; cadence 5/week; originality + n-gram gates with collected inputs |
| WP SEO-meta not REST-writable | P0 write-read round-trip; helper-plugin branch (8.4) — **survives the pivot, still design-gating** |
| Body HTML renders broken on WP | P0 render round-trip before first real batch (8.6) |
| **WP scheduled posts "miss schedule"** (wp-cron unreliable) | P0 item 6: real cron on `wp-cron.php` or missed-schedule guard — the key new operational risk of D4 |
| Internal-link 404s (softskills got bitten) | Intra-batch resolution + 200-check for out-of-batch; back-links as draft revisions, never silent live edits |
| Duplicate post on `/ae-8` rerun | uid search-before-create; `wp_post_id` recorded post-create (8.1) |
| Reuse premise wrong (v1 error) | Section 3 filesystem-verified; baseline now honestly small |
| Cannibalisation via hallucinated keywords | AI-proposed slugs quarantined `status: proposed`, excluded from the dedupe guarantee |
| Dropped autonomous safeguards leave a gap | Intentional: SQLite/costguard/failure-alerts solved daemon problems; the human-batch model has a human, not a daemon, in the loop |

## 12. Build phases

| Phase | Deliverable | Gate |
|---|---|---|
| **P0** | `probe.py` + populated `sites.yaml`/`courses/trainingint.yaml` + WP app password + Pexels key | All Section 9 pass; REST-meta and body-format **decided from live evidence**; wp-cron reliability confirmed |
| P1 | Port softskills `blog-1…4` → `ae-1…4` (WP-targeted outputs), vendor `voice/` + `seo/` DATA | One slug runs research→voice; owner reviews a real `03-voice.md` |
| P2 | `ae-6-seo-pass` + runnable originality/n-gram/voice-damage gates; `ae-batch` | A 5-article batch passes every gate; owner reviews the batch |
| P3 | `wp_publish.py` + `ae-8-publish` | First batch lands as **scheduled** WP posts on trainingint with correct meta/media/links; rerun creates no duplicates; WordPress auto-publishes one on its date |
| P4 | First real 5–15 article batch end-to-end | A reviewed batch is scheduled across weekdays and auto-appears |
| P5 | Multi-site proof | One more site via `sites.yaml` + `courses/<site>.yaml` + P0 only |

## 13. Owner decisions

**Resolved 2026-05-19:** execution = softskills-style human Claude Code batches of 5–15 (D1–D3) · publish = WP `status=future` scheduled posts, 5/week weekdays, WP's own scheduler (D4) · no API key / no cost ceiling (Claude Code usage) · review gate genuinely owned.

**Still open (not blocking P0/P1):**
1. Shared voice rule files across all sites, or per-site overrides from day 1?
2. trainingint blog URL structure / category taxonomy (also resolved empirically by P0 §9.5).
3. Confirm a real cron is (or can be) set on `wp-cron.php` for trainingint, or accept a missed-schedule guard plugin (P0 §9.6).

---

*Section 3 reuse claims filesystem-verified 2026-05-19. v1 audit verdict was REWORK (false reuse premise); v2 hardened an autonomous engine; v3 adopts the owner's softskills-style human-batch model, which dissolves the autonomous-model audit findings while retaining the WordPress-integration findings (F2/F10) that are model-independent. Any future "reuse X" must be re-verified against the filesystem, never inferred.*
