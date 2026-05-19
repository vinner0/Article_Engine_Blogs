# Article Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a human-driven Claude Code slash-command pipeline (modelled on the proven softskills `blog-1…8` workflow) that the owner runs in batches of 5–15 articles, reviews, then publishes into WordPress as future-dated scheduled posts.

**Architecture:** Per spec v3 (`docs/superpowers/specs/2026-05-19-article-engine-design.md`). Generation = Claude Code (no API key). The only Python is: P0 live-site probe, four pure-function gate libraries (n-gram, originality, link-budget, JSON-LD), a thin WP REST client, and an idempotent scheduled-post publisher. Everything else is prompt files + vendored reference DATA. WordPress's own scheduler publishes the dated posts.

**Tech Stack:** Python 3.11+, `requests`, `PyYAML`, `python-dotenv`, `pytest`, `responses` (HTTP mocking). Slash commands = Markdown prompt files. WP REST API v2 + application passwords. Pexels REST (`PEXELS_API_KEY`).

**Reuse-verification note (filesystem-checked 2026-05-19):** `D:/VP/BLOG_AUDIT/` has **0 Python** — nothing is forked from it. Genuine sources: softskills `.claude/commands/blog-{1,2,3,4,6,8}.md` (no blog-5; blog-7 Lighthouse is dropped — no Astro build in WP model), `src/lib/link-budget.ts` + `link-health.ts` (logic to port), `voice/*.md` (6 files), `seo/{checklist.md,link-budget.md,schema-templates.md,audit-budgets.yaml,pillar-map.yaml}`. Every port task below cites the exact verified source path. Any "reuse X" must be re-verified at execution time, never inferred.

---

## File Structure (decomposition locked here)

| File | Responsibility |
|---|---|
| `pyproject.toml`, `requirements.txt`, `.gitignore`, `tests/conftest.py` | Project scaffold + test config |
| `config/sites.yaml` | Per-site registry: WP base URL, app-password env var, link-budget overrides, probe results (written by probe) |
| `courses/trainingint.yaml` | Course → cluster → article topic spine (the topic queue) |
| `voice/` (6 `.md`) + `voice/sync.md` | Vendored softskills voice rules + provenance/sync doc |
| `seo/` (5 files) + `seo/sync.md` | Vendored softskills SEO checklist/link-budget/schema/pillar-map |
| `scripts/lib/ngram.py` | Pure: 8-word shingle overlap (anti-plagiarism + voice-damage) |
| `scripts/lib/originality.py` | Pure: ≥2-of-4 originality gate |
| `scripts/lib/link_budget.py` | Pure: per-site link-budget validator (ported from `link-budget.ts`) |
| `scripts/lib/jsonld.py` | Pure: Article + FAQPage + BreadcrumbList JSON-LD builder |
| `scripts/lib/wp_client.py` | Thin WP REST client: auth, find/create/update post, upload media, get/set meta |
| `scripts/probe.py` | P0 design-gating preflight; writes results into `config/sites.yaml` |
| `scripts/wp_publish.py` | Idempotent scheduled-post publisher (uses wp_client + gates) |
| `.claude/commands/ae-{1,2,3,4,6}-*.md`, `ae-batch.md`, `ae-8-publish.md` | The pipeline (ported/adapted prompts) |
| `wp-helper-plugin/` | CONDITIONAL — only if probe proves SEO-meta not REST-writable (Task 14) |

Pure libs (`ngram`, `originality`, `link_budget`, `jsonld`) are isolated and fully unit-tested with **adversarial tests** (a no-op/buggy implementation must fail). `wp_client`/`wp_publish` are tested against mocked REST. `probe` is tested against mocked REST + a real-site dry run in Task 8.

---

## Phase P0 — Scaffold, config, probe (design-gating)

### Task 1: Project scaffold

**Files:**
- Create: `D:/VP/ARTICLE_ENGINE/requirements.txt`
- Create: `D:/VP/ARTICLE_ENGINE/pyproject.toml`
- Create: `D:/VP/ARTICLE_ENGINE/.gitignore`
- Create: `D:/VP/ARTICLE_ENGINE/tests/conftest.py`
- Create: `D:/VP/ARTICLE_ENGINE/tests/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scaffold.py`:
```python
import importlib
def test_libs_importable():
    for m in ("scripts.lib.ngram", "scripts.lib.originality",
              "scripts.lib.link_budget", "scripts.lib.jsonld"):
        importlib.import_module(m)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/VP/ARTICLE_ENGINE && python -m pytest tests/test_scaffold.py -v`
Expected: FAIL (ModuleNotFoundError — modules not yet created).

- [ ] **Step 3: Create scaffold files**

`requirements.txt`:
```
requests>=2.31
PyYAML>=6.0
python-dotenv>=1.0
pytest>=8.0
responses>=0.25
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`.gitignore`:
```
credentials/.env
__pycache__/
*.pyc
.pytest_cache/
content/
imports/
```

`tests/conftest.py`:
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
```

Create empty package markers: `scripts/__init__.py`, `scripts/lib/__init__.py` (empty files).

- [ ] **Step 4: Re-run test — still fails until libs exist (expected)**

Run: `python -m pytest tests/test_scaffold.py -v`
Expected: still FAIL (libs created in later tasks). This test becomes the green gate at end of Task 6. Leave it; do NOT stub the libs to pass it now.

- [ ] **Step 5: Commit**

```bash
cd D:/VP/ARTICLE_ENGINE && git add -A && git commit -m "chore: project scaffold + deps"
```

---

### Task 2: `config/sites.yaml` and `courses/trainingint.yaml`

**Files:**
- Create: `config/sites.yaml`
- Create: `courses/trainingint.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import yaml, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_sites_yaml_shape():
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())
    s = cfg["sites"]["trainingint"]
    assert s["wp_api_base"].endswith("/wp-json/wp/v2")
    assert s["app_password_env"] == "WP_TRAININGINT"
    assert "link_budget" in s and "probe" in s

def test_courses_yaml_shape():
    c = yaml.safe_load((ROOT / "courses/trainingint.yaml").read_text())
    assert c["site"] == "trainingint"
    course = c["courses"][0]
    for k in ("id", "course_url", "pillar", "cluster", "secondary_courses"):
        assert k in course
    assert course["cluster"][0]["status"] in ("idea", "proposed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (files do not exist).

- [ ] **Step 3: Create the config files**

`config/sites.yaml`:
```yaml
sites:
  trainingint:
    base_url: https://www.trainingint.com
    wp_api_base: https://www.trainingint.com/wp-json/wp/v2
    app_password_env: WP_TRAININGINT          # value in credentials/.env
    cadence:
      per_week: 5
      days: [Mon, Tue, Wed, Thu, Fri]
    link_budget:                              # trainingint as HOST (inverted vs softskills)
      internal_sibling_min: 2
      internal_sibling_max: 3
      primary_course_distinct: 1              # exactly one primary course URL
      primary_course_occurrences_max: 3       # CTA top + bottom + <=1 contextual
      secondary_course_max: 3
      authoritative_outbound_min: 1
      authoritative_outbound_max: 2
    probe:                                    # filled by scripts/probe.py — do NOT hand-edit
      rest_ok: null
      seo_plugin: null                        # yoast | rankmath | none
      seo_meta_rest_writable: null            # true => direct; false => helper plugin (Task 14)
      seo_plugin_emits_graph: null
      html_renders_ok: null
      default_category_id: null
      default_author_id: null
      media_max_bytes: null
      wpcron_reliable: null
      keyword_data: null                      # ubersuggest_csv | ai_only
      probed_at: null
```

`courses/trainingint.yaml` (seed with one real course block; owner extends):
```yaml
site: trainingint
courses:
  - id: writing-professional-emails
    course_url: https://www.trainingint.com/writing-professional-emails
    pillar: communication
    secondary_courses:
      - https://www.trainingint.com/communicate-with-confidence
      - https://www.trainingint.com/business-presentation-skills-training-singapore
    cluster:
      - slug: how-to-write-a-professional-email
        primary_keyword: how to write a professional email
        status: idea
      - slug: how-to-write-a-follow-up-email
        primary_keyword: how to write a follow up email
        status: idea
      - slug: how-to-write-a-formal-email-to-your-boss
        primary_keyword: how to write a formal email to your boss
        status: idea
      - slug: how-to-write-an-apology-email-at-work
        primary_keyword: how to write an apology email
        status: idea
      - slug: how-to-write-a-meeting-recap-email
        primary_keyword: how to write a meeting recap email
        status: idea
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add config/ courses/ tests/test_config.py && git commit -m "feat: site registry + trainingint course spine"
```

---

### Task 3: Vendor voice/ + seo/ DATA from softskills

**Files:**
- Create: `voice/{voice,humor,opinions,stats,stories,do-not-write}.md` (copied), `voice/sync.md`
- Create: `seo/{checklist.md,link-budget.md,schema-templates.md,audit-budgets.yaml,pillar-map.yaml}` (copied), `seo/sync.md`
- Create: `tests/test_vendored_data.py`

- [ ] **Step 1: Write the failing test**

`tests/test_vendored_data.py`:
```python
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
VOICE = ["voice.md","humor.md","opinions.md","stats.md","stories.md","do-not-write.md"]
SEO = ["checklist.md","link-budget.md","schema-templates.md","audit-budgets.yaml","pillar-map.yaml"]

def test_voice_files_present_nonempty():
    for f in VOICE:
        p = ROOT / "voice" / f
        assert p.exists() and p.stat().st_size > 100, f
    assert "24 years" in (ROOT / "voice/stats.md").read_text(encoding="utf-8")

def test_seo_files_present_nonempty():
    for f in SEO:
        p = ROOT / "seo" / f
        assert p.exists() and p.stat().st_size > 100, f
    assert "Refuse-to-publish" in (ROOT / "seo/link-budget.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vendored_data.py -v`
Expected: FAIL (files not copied yet).

- [ ] **Step 3: Copy the verified source files**

Source (verified to exist 2026-05-19): `D:/vp/softskills/1-NEW-SSKILLS/`. Run:
```bash
cd D:/VP/ARTICLE_ENGINE
mkdir -p voice seo
cp "D:/vp/softskills/1-NEW-SSKILLS/voice/"{voice,humor,opinions,stats,stories,do-not-write}.md voice/
cp "D:/vp/softskills/1-NEW-SSKILLS/seo/"{checklist.md,link-budget.md,schema-templates.md,audit-budgets.yaml,pillar-map.yaml} seo/
```

`voice/sync.md`:
```markdown
# Voice DATA provenance
Vendored 2026-05-19 from D:/vp/softskills/1-NEW-SSKILLS/voice/ (6 files).
These are softskills' LOCKED voice rules — stats.md facts are verbatim, never paraphrased.
To resync: re-copy the 6 files; diff before overwriting; never edit here without
updating the softskills source too (single source of truth lives in softskills).
```

`seo/sync.md`:
```markdown
# SEO DATA provenance
Vendored 2026-05-19 from D:/vp/softskills/1-NEW-SSKILLS/seo/.
link-budget.md is softskills.sg-centric; the trainingint link budget is
re-expressed numerically in config/sites.yaml -> sites.trainingint.link_budget
and enforced by scripts/lib/link_budget.py. checklist.md (80 items) is used as-is
by /ae-6-seo-pass. pillar-map.yaml is reference topology only; the live topic
queue is courses/<site>.yaml.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vendored_data.py -v`
Expected: PASS. If `test_voice_files_present_nonempty` fails on the `"24 years"` assertion, the wrong file was copied — re-verify the source path.

- [ ] **Step 5: Commit**

```bash
git add voice/ seo/ tests/test_vendored_data.py && git commit -m "feat: vendor softskills voice + SEO DATA (provenance documented)"
```

---

## Phase P1 — Pure gate libraries (TDD + adversarial)

> Per superpowers-extras: plan code is unvalidated code. Each lib ships an **adversarial test** — a no-op/buggy implementation MUST fail it.

### Task 4: `scripts/lib/ngram.py` — 8-word shingle overlap

**Files:**
- Create: `scripts/lib/ngram.py`
- Create: `tests/test_ngram.py`

- [ ] **Step 1: Write the failing tests (incl. adversarial)**

`tests/test_ngram.py`:
```python
from scripts.lib.ngram import shingles, overlap_8gram, voice_survival_ratio

def test_shingles_basic():
    assert ("the quick brown fox jumps over the lazy",) [0] in \
        {" ".join(s) for s in shingles("the quick brown fox jumps over the lazy dog", 8)}

def test_overlap_detects_shared_phrase():
    a = "you should always proofread your email before you hit send today"
    b = "experts say you should always proofread your email before you hit send"
    hits = overlap_8gram(a, b)
    assert any("proofread your email before you hit send" in h for h in hits)

# ADVERSARIAL: a no-op overlap (returns []) MUST fail this.
def test_overlap_no_op_implementation_fails():
    a = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    b = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    assert overlap_8gram(a, b), "identical text must report >=1 shared 8-gram"

def test_voice_survival_ratio():
    voice = "one two three four five six seven eight nine ten eleven twelve"
    seo = voice  # unchanged prose
    assert voice_survival_ratio(seo, voice) == 1.0
    # ADVERSARIAL: a stub returning 1.0 must fail when prose is gutted
    assert voice_survival_ratio("completely different words entirely none shared at all here now", voice) < 0.85
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ngram.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/lib/ngram.py`:
```python
import re

def _norm(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())

def shingles(text: str, n: int = 8) -> list[tuple[str, ...]]:
    w = _norm(text)
    return [tuple(w[i:i + n]) for i in range(len(w) - n + 1)] if len(w) >= n else []

def overlap_8gram(a: str, b: str, n: int = 8) -> list[str]:
    sb = {s for s in shingles(b, n)}
    return [" ".join(s) for s in shingles(a, n) if s in sb]

def voice_survival_ratio(seo_text: str, voice_text: str, n: int = 8) -> float:
    """Fraction of the voice draft's 8-grams that survive into the SEO draft."""
    vs = shingles(voice_text, n)
    if not vs:
        return 1.0
    se = {s for s in shingles(seo_text, n)}
    return sum(1 for s in vs if s in se) / len(vs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ngram.py -v`
Expected: PASS (4 tests, including both adversarial).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/ngram.py tests/test_ngram.py && git commit -m "feat: 8-gram overlap + voice-survival gate (adversarial-tested)"
```

---

### Task 5: `scripts/lib/originality.py` — ≥2-of-4 gate

**Files:**
- Create: `scripts/lib/originality.py`
- Create: `tests/test_originality.py`

- [ ] **Step 1: Write the failing tests (incl. adversarial)**

`tests/test_originality.py`:
```python
from scripts.lib.originality import originality_report

STORIES = "A trainee once emailed the whole company by mistake. We laughed, then fixed it."
STATS = "24 years training in Singapore. 48,000+ working professionals trained."

def test_passes_with_story_and_stat():
    article = ("Here is a real case: A trainee once emailed the whole company by "
               "mistake. We laughed, then fixed it. Note we have 24 years training "
               "in Singapore behind this advice.")
    r = originality_report(article, stories_md=STORIES, stats_md=STATS,
                           serp_bodies=["generic competitor text about emails"])
    assert r["passes"] is True and r["count"] >= 2

def test_fails_with_zero_elements():
    article = "Generic advice about writing emails that competitors also say."
    r = originality_report(article, stories_md=STORIES, stats_md=STATS,
                           serp_bodies=["Generic advice about writing emails that competitors also say."])
    assert r["passes"] is False and r["count"] == 0

# ADVERSARIAL: a stub returning {"passes": True} unconditionally MUST fail this.
def test_no_op_pass_stub_fails():
    article = "nothing original here at all just filler words repeated repeated"
    r = originality_report(article, stories_md=STORIES, stats_md=STATS,
                           serp_bodies=[article])
    assert r["passes"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_originality.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/lib/originality.py`:
```python
from scripts.lib.ngram import overlap_8gram

def _has_story(article: str, stories_md: str) -> bool:
    for line in (l.strip(" -*") for l in stories_md.splitlines()):
        if len(line) > 30 and line[:30].lower() in article.lower():
            return True
    return False

def _has_stat(article: str, stats_md: str) -> bool:
    for line in (l.strip(" -*") for l in stats_md.splitlines()):
        frag = line.split(".")[0].strip()
        if len(frag) > 6 and frag.lower() in article.lower():
            return True
    return False

def _has_original_analogy(article: str, serp_bodies: list[str]) -> bool:
    cues = ("like ", "is like", "think of it as", "imagine ", "as if ")
    for sent in article.replace("\n", " ").split("."):
        if any(c in sent.lower() for c in cues):
            if not any(overlap_8gram(sent, body) for body in serp_bodies):
                return True
    return False

def _has_framework(article: str, serp_bodies: list[str]) -> bool:
    import re
    if re.search(r"(?m)^\s*(\d+\.|\-|\*)\s+\S", article):
        block = "\n".join(l for l in article.splitlines()
                          if re.match(r"\s*(\d+\.|\-|\*)\s+\S", l))
        return bool(block) and not any(overlap_8gram(block, b) for b in serp_bodies)
    return False

def originality_report(article: str, stories_md: str, stats_md: str,
                       serp_bodies: list[str]) -> dict:
    checks = {
        "story": _has_story(article, stories_md),
        "stat": _has_stat(article, stats_md),
        "original_analogy": _has_original_analogy(article, serp_bodies),
        "original_framework": _has_framework(article, serp_bodies),
    }
    count = sum(checks.values())
    return {"passes": count >= 2, "count": count, "checks": checks}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_originality.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/originality.py tests/test_originality.py && git commit -m "feat: >=2-of-4 originality gate (adversarial-tested)"
```

---

### Task 6: `scripts/lib/link_budget.py` — per-site link-budget validator

Ported from the rules in `D:/vp/softskills/1-NEW-SSKILLS/seo/link-budget.md` (read verbatim 2026-05-19), inverted for trainingint-as-host and parameterised by `config/sites.yaml`'s `link_budget` block.

**Files:**
- Create: `scripts/lib/link_budget.py`
- Create: `tests/test_link_budget.py`

- [ ] **Step 1: Write the failing tests (incl. adversarial)**

`tests/test_link_budget.py`:
```python
from scripts.lib.link_budget import validate_links

BUDGET = {  # mirrors config/sites.yaml sites.trainingint.link_budget
    "internal_sibling_min": 2, "internal_sibling_max": 3,
    "primary_course_distinct": 1, "primary_course_occurrences_max": 3,
    "secondary_course_max": 3,
    "authoritative_outbound_min": 1, "authoritative_outbound_max": 2,
}

def _links(**kw):
    return kw  # convenience

def test_clean_inventory_passes():
    inv = {
        "internal_sibling": ["/blog/a", "/blog/b"],
        "primary_course": ["https://www.trainingint.com/x",
                           "https://www.trainingint.com/x",
                           "https://www.trainingint.com/x"],
        "secondary_course": ["https://www.trainingint.com/y"],
        "authoritative_outbound": ["https://www.skillsfuture.gov.sg/"],
        "anchors": ["write better emails", "the email course", "follow-up guide",
                    "SkillsFuture", "communicate course"],
        "same_paragraph_domains": [],
    }
    assert validate_links(inv, BUDGET) == []

# ADVERSARIAL: a stub returning [] (no violations) MUST fail here.
def test_too_many_primary_course_occurrences_is_violation():
    inv = {
        "internal_sibling": ["/blog/a", "/blog/b"],
        "primary_course": ["https://www.trainingint.com/x"] * 5,   # 5 > max 3
        "secondary_course": [],
        "authoritative_outbound": ["https://mom.gov.sg"],
        "anchors": ["a", "b", "c", "d", "e", "f", "g"],
        "same_paragraph_domains": [],
    }
    v = validate_links(inv, BUDGET)
    assert any("primary_course_occurrences" in x for x in v)

def test_orphan_and_eeat_failures():
    inv = {"internal_sibling": [], "primary_course": ["u"],
           "secondary_course": [], "authoritative_outbound": [],
           "anchors": ["x"], "same_paragraph_domains": []}
    v = validate_links(inv, BUDGET)
    assert any("internal_sibling_min" in x for x in v)
    assert any("authoritative_outbound_min" in x for x in v)

def test_duplicate_anchor_and_same_paragraph_spam():
    inv = {"internal_sibling": ["/a", "/b"], "primary_course": ["u"],
           "secondary_course": [], "authoritative_outbound": ["https://hbr.org"],
           "anchors": ["same", "same"], "same_paragraph_domains": ["trainingint.com"]}
    v = validate_links(inv, BUDGET)
    assert any("identical_anchor" in x for x in v)
    assert any("same_paragraph" in x for x in v)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_link_budget.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/lib/link_budget.py`:
```python
def validate_links(inv: dict, budget: dict) -> list[str]:
    """Return a list of violation codes. Empty list = passes.
    inv keys: internal_sibling[], primary_course[] (one per occurrence),
    secondary_course[], authoritative_outbound[], anchors[],
    same_paragraph_domains[] (domains appearing >1x in one paragraph)."""
    v = []
    sib = inv["internal_sibling"]
    if len(sib) < budget["internal_sibling_min"]:
        v.append(f"internal_sibling_min: {len(sib)} < {budget['internal_sibling_min']}")
    if len(sib) > budget["internal_sibling_max"]:
        v.append(f"internal_sibling_max: {len(sib)} > {budget['internal_sibling_max']}")

    pc = inv["primary_course"]
    if len(set(pc)) > budget["primary_course_distinct"]:
        v.append(f"primary_course_distinct: {len(set(pc))} distinct > "
                 f"{budget['primary_course_distinct']}")
    if len(pc) > budget["primary_course_occurrences_max"]:
        v.append(f"primary_course_occurrences: {len(pc)} > "
                 f"{budget['primary_course_occurrences_max']}")

    if len(inv["secondary_course"]) > budget["secondary_course_max"]:
        v.append(f"secondary_course_max: {len(inv['secondary_course'])} > "
                 f"{budget['secondary_course_max']}")

    ao = inv["authoritative_outbound"]
    if len(ao) < budget["authoritative_outbound_min"]:
        v.append(f"authoritative_outbound_min: {len(ao)} < "
                 f"{budget['authoritative_outbound_min']}")
    if len(ao) > budget["authoritative_outbound_max"]:
        v.append(f"authoritative_outbound_max: {len(ao)} > "
                 f"{budget['authoritative_outbound_max']}")

    anchors = [a.strip().lower() for a in inv["anchors"]]
    if len(anchors) != len(set(anchors)):
        v.append("identical_anchor: two or more link anchors are identical")
    banned = {"click here", "learn more", "read more", "here"}
    if any(a in banned for a in anchors):
        v.append("banned_anchor: generic anchor text present")

    if inv["same_paragraph_domains"]:
        v.append(f"same_paragraph: domain repeated in one paragraph "
                 f"({inv['same_paragraph_domains']})")
    return v
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_link_budget.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/link_budget.py tests/test_link_budget.py && git commit -m "feat: per-site link-budget validator (ported from softskills rules, adversarial-tested)"
```

---

### Task 7: `scripts/lib/jsonld.py` — schema builder

Shapes verified against `D:/vp/softskills/1-NEW-SSKILLS/seo/schema-templates.md` (Article + FAQPage + BreadcrumbList).

**Files:**
- Create: `scripts/lib/jsonld.py`
- Create: `tests/test_jsonld.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_jsonld.py`:
```python
import json
from scripts.lib.jsonld import build_jsonld

def test_emits_three_graph_nodes():
    blocks = build_jsonld(
        url="https://www.trainingint.com/blog/how-to-write-a-professional-email/",
        title="How to Write a Professional Email",
        description="A practical guide.",
        author="Vinai Prakash",
        publisher="Intellisoft Training Pte Ltd",
        faqs=[{"q": "Q1?", "a": "A1."}],
        breadcrumb=[("Home", "https://www.trainingint.com/"),
                    ("Blog", "https://www.trainingint.com/blog/"),
                    ("How to Write a Professional Email",
                     "https://www.trainingint.com/blog/how-to-write-a-professional-email/")],
    )
    types = {b["@type"] for b in json.loads(blocks)["@graph"]}
    assert {"Article", "FAQPage", "BreadcrumbList"} <= types

def test_faqpage_skipped_when_plugin_emits_graph():
    blocks = build_jsonld(url="u", title="t", description="d", author="a",
                          publisher="p", faqs=[{"q": "x", "a": "y"}],
                          breadcrumb=[("Home", "u")], suppress={"FAQPage"})
    types = {b["@type"] for b in json.loads(blocks)["@graph"]}
    assert "FAQPage" not in types and "Article" in types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_jsonld.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/lib/jsonld.py`:
```python
import json

def build_jsonld(url, title, description, author, publisher,
                  faqs, breadcrumb, suppress: set | None = None) -> str:
    suppress = suppress or set()
    graph = []
    if "Article" not in suppress:
        graph.append({
            "@type": "Article", "headline": title, "description": description,
            "mainEntityOfPage": url,
            "author": {"@type": "Person", "name": author},
            "publisher": {"@type": "Organization", "name": publisher},
        })
    if "FAQPage" not in suppress and faqs:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [{
                "@type": "Question", "name": f["q"],
                "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
            } for f in faqs],
        })
    if "BreadcrumbList" not in suppress and breadcrumb:
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [{
                "@type": "ListItem", "position": i + 1, "name": n, "item": u
            } for i, (n, u) in enumerate(breadcrumb)],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graph})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_jsonld.py -v` then full suite `python -m pytest -v`
Expected: PASS; `tests/test_scaffold.py::test_libs_importable` now also PASSES (all four libs exist).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/jsonld.py tests/test_jsonld.py && git commit -m "feat: JSON-LD builder with plugin-graph suppression"
```

---

## Phase P0 (cont.) — WP client + probe

### Task 8: `scripts/lib/wp_client.py` — thin WP REST client

**Files:**
- Create: `scripts/lib/wp_client.py`
- Create: `tests/test_wp_client.py`

- [ ] **Step 1: Write the failing tests (mocked REST)**

`tests/test_wp_client.py`:
```python
import responses
from scripts.lib.wp_client import WPClient

BASE = "https://www.trainingint.com/wp-json/wp/v2"

@responses.activate
def test_find_post_by_uid_returns_id_or_none():
    responses.get(f"{BASE}/posts", json=[{"id": 42}], status=200)
    c = WPClient(BASE, "user", "app pass")
    assert c.find_post_by_uid("abc123") == 42

@responses.activate
def test_find_post_by_uid_none_when_empty():
    responses.get(f"{BASE}/posts", json=[], status=200)
    c = WPClient(BASE, "user", "app pass")
    assert c.find_post_by_uid("zzz") is None

@responses.activate
def test_create_post_returns_id():
    responses.post(f"{BASE}/posts", json={"id": 99}, status=201)
    c = WPClient(BASE, "user", "app pass")
    assert c.create_post({"title": "t", "status": "draft"}) == 99
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wp_client.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/lib/wp_client.py`:
```python
import requests
from requests.auth import HTTPBasicAuth

UID_META = "ae_content_uid"

class WPClient:
    def __init__(self, api_base: str, user: str, app_password: str, timeout: int = 30):
        self.base = api_base.rstrip("/")
        self.auth = HTTPBasicAuth(user, app_password)
        self.timeout = timeout

    def _get(self, path, **params):
        r = requests.get(f"{self.base}{path}", params=params,
                         auth=self.auth, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def me(self) -> dict:
        return self._get("/users/me")

    def find_post_by_uid(self, uid: str):
        # meta_key search requires the meta be registered/searchable; fall back to slug.
        res = self._get("/posts", **{"meta_key": UID_META, "meta_value": uid,
                                     "status": "any", "per_page": 1})
        if res:
            return res[0]["id"]
        return None

    def find_post_by_slug(self, slug: str):
        res = self._get("/posts", slug=slug, status="any", per_page=1)
        return res[0]["id"] if res else None

    def create_post(self, payload: dict) -> int:
        r = requests.post(f"{self.base}/posts", json=payload,
                          auth=self.auth, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["id"]

    def update_post(self, post_id: int, payload: dict) -> int:
        r = requests.post(f"{self.base}/posts/{post_id}", json=payload,
                          auth=self.auth, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["id"]

    def upload_media(self, filename: str, content: bytes, mime: str) -> int:
        r = requests.post(f"{self.base}/media", data=content,
                          headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                   "Content-Type": mime},
                          auth=self.auth, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["id"]

    def read_post_meta(self, post_id: int, key: str):
        return self._get(f"/posts/{post_id}").get("meta", {}).get(key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wp_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/wp_client.py tests/test_wp_client.py && git commit -m "feat: thin WP REST client (mocked-tested)"
```

---

### Task 9: `scripts/probe.py` — P0 design-gating preflight

**Files:**
- Create: `scripts/probe.py`
- Create: `tests/test_probe.py`

- [ ] **Step 1: Write the failing tests (incl. adversarial)**

`tests/test_probe.py`:
```python
import responses, yaml, pathlib
from scripts.probe import probe_meta_writable

BASE = "https://www.trainingint.com/wp-json/wp/v2"

@responses.activate
def test_meta_writable_true_when_readback_matches():
    responses.post(f"{BASE}/posts", json={"id": 7}, status=201)
    responses.post(f"{BASE}/posts/7", json={"id": 7}, status=200)
    responses.get(f"{BASE}/posts/7",
                  json={"id": 7, "meta": {"rank_math_title": "PROBE-TOKEN"}}, status=200)
    responses.delete(f"{BASE}/posts/7", json={"deleted": True}, status=200)
    from scripts.lib.wp_client import WPClient
    wp = WPClient(BASE, "u", "p")
    assert probe_meta_writable(wp, "rank_math_title", "PROBE-TOKEN") is True

# ADVERSARIAL: a probe that hardcodes True must fail when readback does NOT match.
@responses.activate
def test_meta_writable_false_when_readback_mismatches():
    responses.post(f"{BASE}/posts", json={"id": 8}, status=201)
    responses.post(f"{BASE}/posts/8", json={"id": 8}, status=200)
    responses.get(f"{BASE}/posts/8",
                  json={"id": 8, "meta": {"rank_math_title": ""}}, status=200)  # NOT written
    responses.delete(f"{BASE}/posts/8", json={"deleted": True}, status=200)
    from scripts.lib.wp_client import WPClient
    wp = WPClient(BASE, "u", "p")
    assert probe_meta_writable(wp, "rank_math_title", "PROBE-TOKEN") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_probe.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/probe.py`:
```python
"""P0 design-gating preflight. Probes the LIVE site; writes results into
config/sites.yaml. Never assume runtime facts — they come from the target."""
import os, sys, yaml, pathlib, datetime, requests
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient, UID_META

ROOT = pathlib.Path(__file__).resolve().parents[1]

def probe_meta_writable(wp: WPClient, meta_key: str, token: str) -> bool:
    """Create throwaway draft, write meta, READ IT BACK, confirm, delete.
    Returns True only if the readback equals what we wrote."""
    pid = wp.create_post({"title": "AE PROBE — delete me", "status": "draft",
                          "content": "<p>probe</p>", "meta": {meta_key: token}})
    try:
        wp.update_post(pid, {"meta": {meta_key: token}})
        got = wp.read_post_meta(pid, meta_key)
        return got == token
    finally:
        requests.delete(f"{wp.base}/posts/{pid}", params={"force": True},
                        auth=wp.auth, timeout=wp.timeout)

def detect_seo_plugin(wp: WPClient) -> str:
    """Heuristic: probe a post's meta keys / known REST routes."""
    try:
        sample = wp._get("/posts", per_page=1)
        meta = (sample[0].get("meta", {}) if sample else {})
        if any(k.startswith("rank_math") for k in meta):
            return "rankmath"
        if any(k.startswith("_yoast") for k in meta):
            return "yoast"
    except Exception:
        pass
    return "none"

def run(site: str = "trainingint"):
    load_dotenv(ROOT / "credentials/.env")
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())
    s = cfg["sites"][site]
    pw = os.environ.get(s["app_password_env"])
    user = os.environ.get(s["app_password_env"] + "_USER")
    if not pw or not user:
        sys.exit(f"Set {s['app_password_env']} and {s['app_password_env']}_USER "
                 f"in credentials/.env")
    wp = WPClient(s["wp_api_base"], user, pw)

    p = s["probe"]
    try:
        wp.me(); p["rest_ok"] = True
    except Exception as e:
        p["rest_ok"] = False
        print(f"REST/auth FAILED: {e}")
    if p["rest_ok"]:
        plugin = detect_seo_plugin(wp)
        p["seo_plugin"] = plugin
        meta_key = {"rankmath": "rank_math_title",
                    "yoast": "_yoast_wpseo_title"}.get(plugin)
        p["seo_meta_rest_writable"] = (
            probe_meta_writable(wp, meta_key, "AE-PROBE-TOKEN")
            if meta_key else False)
    p["probed_at"] = datetime.date.today().isoformat()

    (ROOT / "config/sites.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    print("PROBE RESULT:", yaml.safe_dump(p, sort_keys=False))
    print("\nMANUAL probe items still required before first batch:")
    print(" - html_renders_ok: push a test HTML draft, view it in wp-admin, set true/false")
    print(" - wpcron_reliable: confirm a real cron hits wp-cron.php (or install "
          "'Missed Scheduled Posts Publisher'); set true/false")
    print(" - default_category_id / default_author_id: read from wp-admin; fill in")
    print(" - keyword_data: ubersuggest_csv if you will drop CSVs, else ai_only")
    print("Edit config/sites.yaml probe block for these, then proceed.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "trainingint")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_probe.py -v`
Expected: PASS (2 tests, incl. adversarial mismatch case).

- [ ] **Step 5: Commit**

```bash
git add scripts/probe.py tests/test_probe.py && git commit -m "feat: P0 live-site probe with meta write-readback (adversarial-tested)"
```

- [ ] **Step 6: Live run (owner prerequisite — not automatable)**

Owner creates a WP application password on trainingint.com (Users → Profile → Application Passwords), puts into `credentials/.env`:
```
WP_TRAININGINT=xxxx xxxx xxxx xxxx
WP_TRAININGINT_USER=vinai
```
Run: `python scripts/probe.py trainingint`
Expected: `config/sites.yaml` `probe:` block filled; console prints the manual items. **GATE: do not start Phase P3 (publish) until `rest_ok: true` and `seo_meta_rest_writable` is decided.** If `seo_meta_rest_writable: false` → Task 14 (helper plugin) becomes required.

---

## Phase P3 — Publisher

### Task 10: `scripts/wp_publish.py` — idempotent scheduled-post publisher

**Files:**
- Create: `scripts/wp_publish.py`
- Create: `tests/test_wp_publish.py`

- [ ] **Step 1: Write the failing tests — THE duplicate-post adversarial test**

`tests/test_wp_publish.py`:
```python
import responses
from scripts.lib.wp_client import WPClient
from scripts.wp_publish import publish_article

BASE = "https://www.trainingint.com/wp-json/wp/v2"

def _wp():
    return WPClient(BASE, "u", "p")

@responses.activate
def test_first_publish_creates_scheduled_post():
    responses.get(f"{BASE}/posts", json=[], status=200)          # uid not found
    created = responses.post(f"{BASE}/posts", json={"id": 100}, status=201)
    pid = publish_article(_wp(), uid="uid-1", slug="how-to-x",
                          title="How to X", html="<p>body</p>",
                          meta={}, scheduled_iso="2026-06-01T09:00:00",
                          category_id=5, author_id=1)
    assert pid == 100
    assert created.call_count == 1
    body = responses.calls[-1].request.body
    assert b'"status": "future"' in body and b"2026-06-01T09:00:00" in body

# ADVERSARIAL: a publisher that always POSTs /posts creates a DUPLICATE.
# This test MUST fail such an implementation.
@responses.activate
def test_rerun_with_same_uid_updates_not_duplicates():
    responses.get(f"{BASE}/posts", json=[{"id": 100}], status=200)  # uid FOUND
    create = responses.post(f"{BASE}/posts", json={"id": 999}, status=201)
    update = responses.post(f"{BASE}/posts/100", json={"id": 100}, status=200)
    pid = publish_article(_wp(), uid="uid-1", slug="how-to-x",
                          title="How to X", html="<p>body</p>",
                          meta={}, scheduled_iso="2026-06-01T09:00:00",
                          category_id=5, author_id=1)
    assert pid == 100, "must return the EXISTING post id"
    assert create.call_count == 0, "must NOT create a second post on rerun"
    assert update.call_count == 1, "must update the existing post"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wp_publish.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

`scripts/wp_publish.py`:
```python
"""Idempotent scheduled-post publisher. Search-before-create on content_uid
guarantees a rerun never duplicates a post (the key audit finding F6)."""
import hashlib
from scripts.lib.wp_client import WPClient, UID_META

def content_uid(site: str, slug: str) -> str:
    return hashlib.sha1(f"{site}:{slug}".encode()).hexdigest()[:16]

def publish_article(wp: WPClient, uid: str, slug: str, title: str, html: str,
                    meta: dict, scheduled_iso: str, category_id: int,
                    author_id: int) -> int:
    payload = {
        "title": title, "slug": slug, "content": html,
        "status": "future", "date": scheduled_iso,
        "categories": [category_id], "author": author_id,
        "meta": {**meta, UID_META: uid},
    }
    existing = wp.find_post_by_uid(uid) or wp.find_post_by_slug(slug)
    if existing is not None:
        return wp.update_post(existing, payload)
    return wp.create_post(payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wp_publish.py -v`
Expected: PASS — both, including `test_rerun_with_same_uid_updates_not_duplicates` (proves no duplicate post on rerun).

- [ ] **Step 5: Commit**

```bash
git add scripts/wp_publish.py tests/test_wp_publish.py && git commit -m "feat: idempotent scheduled-post publisher (duplicate-post adversarial test green)"
```

---

## Phase P1/P2 — Pipeline slash-command ports

> These are prompt files, not unit-testable code. Each task: copy the **verified** softskills source, apply the listed transforms, then run the structural verification. The verification step is the gate.

### Task 11: Port `ae-1` … `ae-4`

**Files:**
- Create: `.claude/commands/ae-1-keyword-research.md` (from softskills `blog-1-keyword-research.md`)
- Create: `.claude/commands/ae-2-serp-analyze.md` (from `blog-2-serp-analyze.md`)
- Create: `.claude/commands/ae-3-draft.md` (from `blog-3-draft.md`)
- Create: `.claude/commands/ae-4-voice-pass.md` (from `blog-4-voice-pass.md`)

- [ ] **Step 1: Copy verified sources**

```bash
cd D:/VP/ARTICLE_ENGINE && mkdir -p .claude/commands
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-1-keyword-research.md" .claude/commands/ae-1-keyword-research.md
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-2-serp-analyze.md"     .claude/commands/ae-2-serp-analyze.md
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-3-draft.md"            .claude/commands/ae-3-draft.md
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-4-voice-pass.md"       .claude/commands/ae-4-voice-pass.md
```

- [ ] **Step 2: Apply these exact transforms to all four files**

In each `ae-*.md`, find-and-replace (literal):
1. `softskills.sg blog pipeline` → `Article Engine pipeline (trainingint.com)`
2. `src/content/blog/$ARGUMENTS/` → `content/trainingint/$ARGUMENTS/`
3. `seo/pillar-map.yaml` → `courses/trainingint.yaml` (topic source is the course spine, not the softskills pillar-map)
4. Authoritative-spec line → `**Authoritative spec:** docs/superpowers/specs/2026-05-19-article-engine-design.md`
5. Remove any `K1 fixture` / `how-to-speak-confidently-in-meetings` canonical-fixture lines (softskills-specific; no fixture exists here yet — replace with: "No canonical fixture yet; follow the output shape described below.")
6. In `ae-2`, add to Outputs: "Also write `content/trainingint/$ARGUMENTS/_research/serp-bodies/{1,2,3}.txt` — the full extracted body text of the top-3 results (required input for the /ae-6 originality + n-gram gates)."
7. In `ae-3`, keep the Pexels image step verbatim (uses `PEXELS_API_KEY` from `credentials/.env`, same as softskills).

- [ ] **Step 3: Verify**

Run:
```bash
grep -L "Article Engine pipeline" .claude/commands/ae-{1,2,3,4}-*.md   # expect: no output (all transformed)
grep -l "softskills.sg\|pillar-map.yaml\|how-to-speak-confidently" .claude/commands/ae-*.md  # expect: no output
test -f .claude/commands/ae-2-serp-analyze.md && grep -q "serp-bodies" .claude/commands/ae-2-serp-analyze.md && echo "ae-2 serp-bodies OK"
```
Expected: first two greps print nothing; third prints `ae-2 serp-bodies OK`.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/ae-{1,2,3,4}-*.md && git commit -m "feat: port ae-1..4 pipeline commands from softskills (WP-targeted)"
```

---

### Task 12: Port `ae-6-seo-pass` (gates now call the Python libs)

**Files:**
- Create: `.claude/commands/ae-6-seo-pass.md` (from softskills `blog-6-seo-pass.md`)

- [ ] **Step 1: Copy verified source**

```bash
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-6-seo-pass.md" .claude/commands/ae-6-seo-pass.md
```

- [ ] **Step 2: Apply transforms**

1. Same global replaces as Task 11 Step 2 (items 1–5).
2. Output `_draft/04-seo.md` → `_draft/04-seo.html` (WP body is HTML, not MDX).
3. Replace the "VOICE-DAMAGE CHECK" section's manual instruction with: "Compute the voice-survival ratio programmatically: `python -c \"from scripts.lib.ngram import voice_survival_ratio; import pathlib; print(voice_survival_ratio(open('content/trainingint/$ARGUMENTS/_draft/04-seo.html').read(), open('content/trainingint/$ARGUMENTS/_draft/03-voice.md').read()))\"`. If < 0.85, STOP and show the diff; do not write 04-seo.html."
4. Replace the `src/lib/link-budget.ts` / `npx tsx` validator block with: "Build the link inventory dict and run `python -c \"import yaml,json; from scripts.lib.link_budget import validate_links; ...\"` against `config/sites.yaml` `sites.trainingint.link_budget`. If it returns any violations, fix and revalidate before writing."
5. Replace the originality-gate prose with: "Run `scripts.lib.originality.originality_report(article, stories_md, stats_md, serp_bodies)` where `serp_bodies` = the three files in `_research/serp-bodies/`. If `passes` is False, surface back to the user — do not paper over."
6. Replace "Schema is auto-emitted by BlogLayout" with: "Build JSON-LD with `scripts.lib.jsonld.build_jsonld(...)`; pass `suppress={'FAQPage','BreadcrumbList'}` for any type the active SEO plugin already emits per `config/sites.yaml` `probe.seo_plugin_emits_graph`. Embed the returned `<script type=\"application/ld+json\">` block at the end of the HTML body."
7. Keep the 80-item checklist step pointed at `seo/checklist.md` (vendored, unchanged).
8. Keep the "confirm Stage 5 human edit is done" gate verbatim — this is the D3 review gate.

- [ ] **Step 3: Verify**

Run:
```bash
grep -q "voice_survival_ratio" .claude/commands/ae-6-seo-pass.md && \
grep -q "originality_report" .claude/commands/ae-6-seo-pass.md && \
grep -q "build_jsonld" .claude/commands/ae-6-seo-pass.md && \
grep -q "04-seo.html" .claude/commands/ae-6-seo-pass.md && \
! grep -q "npx tsx\|BlogLayout\|04-seo.md\b" .claude/commands/ae-6-seo-pass.md && echo "ae-6 OK"
```
Expected: prints `ae-6 OK`.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/ae-6-seo-pass.md && git commit -m "feat: port ae-6-seo-pass; gates call the Python libs"
```

---

### Task 13: Author `ae-batch.md` and `ae-8-publish.md`

`ae-8-publish` is a heavy rewrite of softskills `blog-8-publish.md` (read verbatim 2026-05-19): drop Lighthouse gate, MDX promotion, Astro build, git/Coolify, GSC (none apply to WP). Keep: cadence guard, originality re-check, link-budget, schema validation, slug uniqueness, pillar(→course) registration. Replace publish actions with a `scripts/wp_publish.py` call.

**Files:**
- Create: `.claude/commands/ae-8-publish.md`
- Create: `.claude/commands/ae-batch.md`

- [ ] **Step 1: Write `ae-8-publish.md`**

```markdown
---
description: Stage 8 — push reviewed batch to WordPress as future-dated scheduled posts. Strict pre-flight gates. Idempotent (no duplicate posts on rerun).
argument-hint: <slug> [--override]
---

# /ae-8-publish

You are running **Stage 8** for slug `$ARGUMENTS` on trainingint.com.

**Authoritative spec:** docs/superpowers/specs/2026-05-19-article-engine-design.md §8

## Inputs
- content/trainingint/$ARGUMENTS/_draft/04-seo.html (Stage 6 output)
- content/trainingint/$ARGUMENTS/_research/serp-bodies/ (gate inputs)
- config/sites.yaml (probe results + link budget; REFUSE if probe.rest_ok != true)
- courses/trainingint.yaml (slug must be registered with matching primary_keyword)
- status/trainingint.yaml (cadence + scheduled-date assignment)

## PRE-FLIGHT GATES (all must pass — refuse if any fail; only --override bypasses cadence)
1. **Probe gate:** config/sites.yaml sites.trainingint.probe.rest_ok must be true and
   seo_meta_rest_writable must be non-null. If seo_meta_rest_writable is false, the
   helper plugin (wp-helper-plugin/) must be installed first — confirm, else REFUSE.
2. **Cadence guard (HARD):** count status=scheduled/published in status/trainingint.yaml
   with a date in the last 7 days. If > 5 (the per_week cap), REFUSE unless --override.
3. **Originality:** run scripts.lib.originality.originality_report; REFUSE if not passes.
4. **Voice-damage:** scripts.lib.ngram.voice_survival_ratio(04-seo.html, 03-voice.md)
   must be >= 0.85, else REFUSE.
5. **Link budget:** scripts.lib.link_budget.validate_links must return [] against
   sites.trainingint.link_budget, else REFUSE (list the violations).
6. **Anti-plagiarism:** scripts.lib.ngram.overlap_8gram(article, each serp-bodies file)
   must be empty; if any 8-gram shared, REFUSE and name the phrase.
7. **Slug uniqueness:** slug not already published on the site (wp_client.find_post_by_slug
   returns None OR the found post carries this slug's content_uid — i.e. it's our own
   prior scheduled post, which is allowed = idempotent update).
8. **Course registration:** slug exists in courses/trainingint.yaml with matching
   primary_keyword and a course_url; REFUSE if missing.

## Publish action (single idempotent call)
Compute scheduled date = next free weekday slot from status/trainingint.yaml (5/week,
Mon–Fri, 09:00 local). Then run:
```bash
python -c "
from scripts.lib.wp_client import WPClient
from scripts.wp_publish import publish_article, content_uid
import os,yaml,pathlib
# load config + .env, build WPClient, read 04-seo.html + meta + category/author
# from config/sites.yaml probe block, then:
pid = publish_article(wp, content_uid('trainingint','$ARGUMENTS'), '$ARGUMENTS',
        title, html, meta, scheduled_iso, category_id, author_id)
print('post id', pid)
"
```
This is idempotent: a rerun with the same slug UPDATES the existing scheduled post,
never creates a duplicate (enforced + adversarial-tested in scripts/wp_publish.py).

## After publish
- Update status/trainingint.yaml: slug → status: scheduled, scheduled_date, wp_post_id
- Surface: post id, scheduled date, the wp-admin edit URL
  (https://www.trainingint.com/wp-admin/post.php?post=<id>&action=edit), and a reminder
  that WordPress will auto-publish on the scheduled date IF wp-cron is reliable
  (config/sites.yaml probe.wpcron_reliable).

## Refuse to proceed if
- Any gate fails (say which gate and the exact failure)
- probe.rest_ok != true (run scripts/probe.py first)
```

- [ ] **Step 2: Write `ae-batch.md`**

```markdown
---
description: Drive 5–15 slugs through ae-1..ae-6, stopping at the human review gate, then list what's ready for ae-8.
argument-hint: <course-id or comma-separated slugs>
---

# /ae-batch

You are running a **batch** for `$ARGUMENTS` on trainingint.com.

## Process
1. Resolve slugs: if $ARGUMENTS is a course id, take that course's `status: idea`
   slugs from courses/trainingint.yaml (skip `status: proposed` — quarantined).
   Cap the batch at 15.
2. For each slug, in order, run the equivalent of: /ae-1 → /ae-2 → /ae-3 → /ae-4.
   Use parallel sub-agents per slug where independent (softskills did this).
   Each stage writes its artifact before the next; safe to resume.
3. **STOP at the human review gate.** Print a table: slug | title | primary_keyword |
   draft path (content/trainingint/<slug>/_draft/03-voice.md). Tell the owner:
   "Edit each 03-voice.md. When done, run /ae-6-seo-pass <slug> per slug, then
   /ae-8-publish <slug> per accepted slug."
4. Do NOT run /ae-6 or /ae-8 automatically — those are post-review.

## Refuse
- If config/sites.yaml probe.rest_ok != true, warn that publishing is blocked until
  /scripts/probe.py passes (research/draft may still proceed).
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -q "find_post_by_slug returns None OR the found post carries" .claude/commands/ae-8-publish.md && \
grep -q "status: proposed" .claude/commands/ae-batch.md && \
! grep -qi "lighthouse\|coolify\|index.mdx\|npm run build\|GSC indexing" .claude/commands/ae-8-publish.md && \
echo "ae-8 + ae-batch OK"
```
Expected: prints `ae-8 + ae-batch OK` (confirms Astro/Lighthouse/Coolify removed, quarantine + idempotency present).

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/ae-8-publish.md .claude/commands/ae-batch.md && git commit -m "feat: ae-8-publish (WP scheduled, idempotent) + ae-batch driver"
```

---

## Phase P3 (conditional) — Helper plugin

### Task 14: WP helper plugin — ONLY IF `probe.seo_meta_rest_writable == false`

Skip entirely if the Task 9 live probe set `seo_meta_rest_writable: true`. Do not build speculatively.

**Files (conditional):**
- Create: `wp-helper-plugin/ae-helper.php`

- [ ] **Step 1: Confirm the runtime fact from the target, not assumption**

Run: `python -c "import yaml; print(yaml.safe_load(open('config/sites.yaml'))['sites']['trainingint']['probe']['seo_meta_rest_writable'])"`
- If `True` → **STOP. This task is not needed.** Mark complete-skipped.
- If `False` → proceed. Also confirm the server PHP version (do not assume): owner runs in wp-admin → Tools → Site Health → Info → Server, reports PHP version; the plugin header below targets PHP 7.4+ (broadest WP-safe baseline) — adjust only if Site Health shows otherwise.

- [ ] **Step 2: Write the plugin**

`wp-helper-plugin/ae-helper.php`:
```php
<?php
/**
 * Plugin Name: Article Engine Helper
 * Description: Hardened REST endpoint to set SEO-plugin meta the public REST API blocks.
 * Version: 1.0.0
 * Requires PHP: 7.4
 */
if (!defined('ABSPATH')) exit;

add_action('rest_api_init', function () {
    register_rest_route('ae/v1', '/meta/(?P<id>\d+)', [
        'methods'  => 'POST',
        'permission_callback' => function () {
            return current_user_can('edit_posts'); // app-password user must have this cap
        },
        'callback' => function (WP_REST_Request $r) {
            $id = (int) $r['id'];
            $meta = $r->get_json_params()['meta'] ?? [];
            if (!is_array($meta) || get_post_status($id) === false) {
                return new WP_Error('ae_bad', 'bad request', ['status' => 400]);
            }
            foreach ($meta as $k => $v) {
                update_post_meta($id, sanitize_key($k), wp_kses_post($v));
            }
            return ['ok' => true, 'id' => $id];
        },
    ]);
});
```

- [ ] **Step 3: Wire the publisher to use it (conditional branch)**

Modify `scripts/wp_publish.py` — add after the `publish_article` create/update returns `pid`, when `site_cfg["probe"]["seo_meta_rest_writable"]` is False, POST the meta to `/ae/v1/meta/{pid}` instead of relying on the core `meta` field. Add this function and call it from `ae-8`'s publish step:
```python
import requests
def push_meta_via_helper(wp, post_id: int, meta: dict) -> None:
    base = wp.base.replace("/wp/v2", "")  # -> https://site/wp-json
    r = requests.post(f"{base}/ae/v1/meta/{post_id}", json={"meta": meta},
                      auth=wp.auth, timeout=wp.timeout)
    r.raise_for_status()
```
Add `tests/test_wp_publish.py` case (responses-mocked) asserting `push_meta_via_helper` POSTs to `/ae/v1/meta/100` and raises on non-2xx.

- [ ] **Step 4: Verify + commit**

Run: `python -m pytest tests/test_wp_publish.py -v` → PASS.
Owner installs `wp-helper-plugin/` on trainingint (zip the folder → Plugins → Upload → Activate), re-runs `python scripts/probe.py trainingint`, confirms meta now writes via helper.
```bash
git add wp-helper-plugin/ scripts/wp_publish.py tests/test_wp_publish.py && git commit -m "feat: conditional WP helper plugin for blocked SEO meta"
```

---

## Phase P4/P5 — Integration runbook (owner-driven, not unit-tested)

### Task 15: First real batch end-to-end (P4)

- [ ] **Step 1:** Owner completes Task 9 Step 6 manual probe items in `config/sites.yaml` (`html_renders_ok`, `wpcron_reliable`, `default_category_id`, `default_author_id`, `keyword_data`). For `html_renders_ok`: run `/ae-8-publish` on ONE throwaway slug, open the wp-admin edit URL, confirm the HTML + JSON-LD render in the post editor and front-end preview; set true/false; if false, escalate (body-format branch — do not proceed).
- [ ] **Step 2:** Run `/ae-batch writing-professional-emails` → produces 5 drafts to `content/trainingint/<slug>/_draft/03-voice.md`, stops at review gate.
- [ ] **Step 3:** Owner does a genuine edit pass on each `03-voice.md` (D3 — this is the real scaled-content-abuse defence; not optional).
- [ ] **Step 4:** Per accepted slug: `/ae-6-seo-pass <slug>` then `/ae-8-publish <slug>`. Confirm in `status/trainingint.yaml` each is `scheduled` with a distinct weekday date and a `wp_post_id`.
- [ ] **Step 5:** On the first scheduled date, confirm the post auto-published (front-end URL live). If it "missed schedule", `probe.wpcron_reliable` was wrong — install the missed-schedule guard plugin and re-confirm.
- [ ] **Step 6:** Commit the run artifacts: `git add content/ status/ && git commit -m "content: first trainingint batch (writing-professional-emails cluster)"`

### Task 16: Multi-site proof (P5)

- [ ] **Step 1:** Add a second site block to `config/sites.yaml` (e.g. `intellisoft`) with its `wp_api_base`, `app_password_env`, `link_budget`, empty `probe`.
- [ ] **Step 2:** Create `courses/intellisoft.yaml` (same shape as trainingint).
- [ ] **Step 3:** Owner creates the WP app password for that site; run `python scripts/probe.py intellisoft`; resolve manual probe items.
- [ ] **Step 4:** Run `/ae-batch <course-id>` then review → `/ae-6` → `/ae-8-publish` for that site (the commands already parameterise the site via the slug's course file; confirm no trainingint-specific hardcode leaked — `grep -rn "trainingint" .claude/commands/` should only show example text, not logic). **Gate:** zero code changes were needed to onboard the second site.
- [ ] **Step 5:** `git commit -m "feat: multi-site proof (second site via config only)"`

---

## Self-Review (performed against spec v3)

**1. Spec coverage:** §3 reuse → Tasks 3,11,12,13 cite verified sources only. §5 topology → Tasks 1–13 create exactly the spec's file tree. §6 cluster spine + quarantine → Task 2 (`status: proposed`) + Task 13 ae-batch skip. §7 stages → Tasks 11,12,13. §7.1 gates (originality/n-gram/voice-damage/link-budget) → Tasks 4,5,6 with adversarial tests, wired in Task 12. §8 wp_publish (idempotent create, scheduled, internal-link discipline) → Task 10 (+ duplicate-post adversarial test) and ae-8 gate 7. §9 P0 probe (incl. meta write-readback, manual render/wpcron) → Task 9. §10 voice/SEO DATA + sync.md → Task 3. §11 risks: duplicate-post (Task 10 test), meta-not-writable branch (Task 14), wpcron (Task 15 Step 5). §12 phases P0–P5 → Tasks 1–16. No spec section left without a task.

**2. Placeholder scan:** No "TBD/handle errors/similar to". Conditional Task 14 has an explicit skip gate, not a placeholder. Runbook tasks (15,16) are owner-driven by nature (live site, app passwords) and say so explicitly with concrete commands.

**3. Type consistency:** `WPClient` methods (`me/find_post_by_uid/find_post_by_slug/create_post/update_post/upload_media/read_post_meta`) defined in Task 8 are exactly those called in Tasks 9,10,14. `publish_article(wp, uid, slug, title, html, meta, scheduled_iso, category_id, author_id)` signature in Task 10 matches its test and the ae-8 call. `UID_META`/`content_uid` consistent across Tasks 8,10. `originality_report`/`validate_links`/`voice_survival_ratio`/`overlap_8gram`/`build_jsonld` signatures match between defining task, tests, and the ae-6 wiring in Task 12.

**4. Adversarial coverage (superpowers-extras: plan code is unvalidated code):** every gate lib + the publisher ships a test a no-op/buggy impl fails — n-gram (`test_overlap_no_op_implementation_fails`), originality (`test_no_op_pass_stub_fails`), link-budget (`test_too_many_primary_course_occurrences_is_violation`), probe (`test_meta_writable_false_when_readback_mismatches`), publisher (`test_rerun_with_same_uid_updates_not_duplicates`). Runtime facts (REST/meta/render/wpcron/PHP version) are taken from the live target via Task 9 + Task 14 Step 1, never assumed.
