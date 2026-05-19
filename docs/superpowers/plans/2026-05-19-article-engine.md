# Article Engine Implementation Plan (v2 — post plan-audit)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
> **Execute strictly by Task number** (phases are labels, not execution order — task deps are satisfied in numeric order).
> **All shell steps run via the Bash tool, not PowerShell** (uses `cp {a,b}`, `grep -li`, heredocs, `sed`).

**Goal:** A human-driven Claude Code slash-command pipeline (modelled on the proven softskills `blog-1…8` workflow) that the owner runs in batches of 5–15 articles, reviews, then publishes into WordPress as future-dated scheduled posts.

**Architecture:** Per spec v3 (`docs/superpowers/specs/2026-05-19-article-engine-design.md`). Generation = Claude Code (no API key). Python only for: a small always-installed WP helper plugin, a live-site probe, four pure gate libs, a thin WP REST client, an idempotent scheduled-post publisher. WordPress's own scheduler publishes the dated posts.

**Tech Stack:** Python 3.11+, `requests`, `PyYAML`, `python-dotenv`, `pytest`, `responses`. PHP 7.4+ (helper plugin). Slash commands = Markdown prompt files. WP REST v2 + application passwords. Pexels REST (`PEXELS_API_KEY`).

**v2 changes (from independent plan audit 2026-05-19):** B1/B2 — port transforms made deterministic, verify steps aligned to real source strings. M3 — idempotency reworked: an **always-installed** helper plugin registers `ae_content_uid` (show_in_rest) and a server-side `/ae/v1/find` route, because stock WP REST cannot query unregistered meta and silently drops it. M4 — Task 11 now uploads featured media + resolves internal links. M5 — ae-8 hard-gates on all required probe fields. M6/M7/M8 — ae-6 link-section retargeted to trainingint; Bash-tool note; jsonld gets a real adversarial test.

**v2.1 fixes (second adversarial pre-build audit 2026-05-19, source-file-verified):** **B1** Task 12 sed now also rewrites the *bare* `pillar-map.yaml` (blog-1 L45 had it un-prefixed; the Step-3 verify-grep matched it but the old sed didn't → gate would false-fail 100%). **m1** Task 13 sed adds `softskills_sg→trainingint` so the `! grep softskills` verify is deterministic regardless of the prose-replace (blog-6 L40 `?utm_source=softskills_sg`). **M1** `seo_plugin_emits_graph` (spec §9.3) was declared but never populated/gated → ae-6 `suppress=` was dead; now an owner-filled probe field gated in Task 14 gate 1 + Task 15 Step 1. **M2** spec §8.2 inline images had no implementing step (live posts would 404 inline `<img>`); Task 11 gains `resolve_inline_media` (ae:img: placeholder → uploaded WP media URL) + test, ae-6 emits the placeholders, ae-8 passes `images_dir`. **M3** spec §8.3 `tags` never set; Task 11 `publish_article` gains `tags=` + test, ae-8 passes it. **N1 (per-task quality review, Task 4)** `scripts/lib/ngram._norm` tokenized HTML tags/entities as words, so the §7.1 voice-damage gate `voice_survival_ratio(04-seo.html, 03-voice.md) ≥ 0.85` (Task 13/14) would false-positive and block *every* article; `voice_survival_ratio` also used a list (dup) denominator and `overlap_8gram` returned dups. Fixed: `_norm` strips tags + `html.unescape` + NFKD-ascii fold (prose-not-markup, plain-text no-op); voice denominator = distinct shingles; overlap deduped. New ADVERSARIAL test encodes the real HTML-vs-markdown calling convention (the original plain-string-only suite was the blind spot that hid this through a "post-audit verified" plan). **N2 (per-task quality review, Task 5)** same defect class in `scripts/lib/originality.py`: `_has_framework` matched only markdown `1./-/*` so it returned False on the real HTML `04-seo.html` (silently degrading the ≥2-of-4 gate); `_has_stat` matched any >6-char fragment so non-numeric `stats.md` lines (course names, bio, headers) false-passed; `_has_analogy` fired on "like you"; `_has_story` matched YAML-key noise. Fixed: framework counts HTML `<li>` + markdown; stat requires a digit; analogy requires a `like a/an/the` simile (or explicit cue); story skips YAML/header/blockquote lines. New real-input adversarial tests (real voice files + HTML article). **C2a left for owner:** `_has_story` is still verbatim-prefix (won't detect paraphrased signature stories) — flagged in Task 5 for an owner design decision, deliberately NOT auto-redesigned.

**Reuse-verification (filesystem-checked + audit-confirmed 2026-05-19):** `D:/VP/BLOG_AUDIT/` = 0 Python, nothing forked. Verified sources used: softskills `.claude/commands/blog-{1,2,3,4,6,8}-*.md`, `voice/*.md` (6), `seo/{checklist,link-budget,schema-templates}.md + audit-budgets.yaml + pillar-map.yaml`. Audit confirmed all exist; transform strings below were checked against the real files.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml`,`requirements.txt`,`.gitignore`,`tests/conftest.py` | Scaffold + test config |
| `config/sites.yaml` | Per-site registry + probe results |
| `courses/trainingint.yaml` | Course→cluster→article topic spine |
| `voice/` (6 md)+`voice/sync.md`, `seo/` (5)+`seo/sync.md` | Vendored softskills DATA + provenance |
| `scripts/lib/ngram.py` | 8-gram overlap (anti-plagiarism + voice-damage) |
| `scripts/lib/originality.py` | ≥2-of-4 originality gate |
| `scripts/lib/link_budget.py` | Per-site link-budget validator |
| `scripts/lib/jsonld.py` | Article+FAQPage+BreadcrumbList builder |
| `scripts/lib/wp_client.py` | WP REST + `/ae/v1/find` client |
| `wp-helper-plugin/ae-helper.php` | **Always installed.** Registers `ae_content_uid` (REST) + `/ae/v1/find` route; conditional `/ae/v1/meta` route |
| `scripts/probe.py` | P0 design-gating preflight (incl. uid round-trip) |
| `scripts/wp_publish.py` | Idempotent scheduled-post publisher + media + link resolution |
| `.claude/commands/ae-{1,2,3,4,6}-*.md`,`ae-batch.md`,`ae-8-publish.md` | Pipeline prompts |

---

### Task 1: Project scaffold

**Files:** Create `requirements.txt`, `pyproject.toml`, `.gitignore`, `tests/conftest.py`, `tests/test_scaffold.py`, `scripts/__init__.py`, `scripts/lib/__init__.py`

- [ ] **Step 1: Write the failing test** — `tests/test_scaffold.py`:
```python
import importlib
def test_libs_importable():
    for m in ("scripts.lib.ngram","scripts.lib.originality",
              "scripts.lib.link_budget","scripts.lib.jsonld"):
        importlib.import_module(m)
```
- [ ] **Step 2: Run, verify fail** — `cd D:/VP/ARTICLE_ENGINE && python -m pytest tests/test_scaffold.py -v` → FAIL (ModuleNotFoundError).
- [ ] **Step 3: Create files**

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
Create empty `scripts/__init__.py`, `scripts/lib/__init__.py`.
- [ ] **Step 4: Re-run** — still FAIL until Task 7 (libs created). Do NOT stub libs to pass. This is the green gate at end of Task 7.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "chore: scaffold + deps"`

---

### Task 2: `config/sites.yaml` + `courses/trainingint.yaml`

**Files:** Create `config/sites.yaml`, `courses/trainingint.yaml`, `tests/test_config.py`

- [ ] **Step 1: Failing test** — `tests/test_config.py`:
```python
import yaml, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
def test_sites_yaml_shape():
    s = yaml.safe_load((ROOT/"config/sites.yaml").read_text())["sites"]["trainingint"]
    assert s["wp_api_base"].endswith("/wp-json/wp/v2")
    assert s["app_password_env"] == "WP_TRAININGINT"
    assert "link_budget" in s and "probe" in s
    for k in ("rest_ok","seo_meta_rest_writable","uid_roundtrip_ok",
              "seo_plugin_emits_graph","default_category_id","default_author_id",
              "html_renders_ok","wpcron_reliable","keyword_data"):
        assert k in s["probe"], k
def test_courses_yaml_shape():
    c = yaml.safe_load((ROOT/"courses/trainingint.yaml").read_text())
    assert c["site"] == "trainingint"
    course = c["courses"][0]
    for k in ("id","course_url","pillar","cluster","secondary_courses"):
        assert k in course
    assert course["cluster"][0]["status"] in ("idea","proposed")
```
- [ ] **Step 2: Run, verify fail** — `python -m pytest tests/test_config.py -v` → FAIL.
- [ ] **Step 3: Create files** —

`config/sites.yaml`:
```yaml
sites:
  trainingint:
    base_url: https://www.trainingint.com
    wp_api_base: https://www.trainingint.com/wp-json/wp/v2
    ae_api_base: https://www.trainingint.com/wp-json/ae/v1
    app_password_env: WP_TRAININGINT
    cadence: { per_week: 5, days: [Mon,Tue,Wed,Thu,Fri] }
    link_budget:
      internal_sibling_min: 2
      internal_sibling_max: 3
      primary_course_distinct: 1
      primary_course_occurrences_max: 3
      secondary_course_max: 3
      authoritative_outbound_min: 1
      authoritative_outbound_max: 2
    probe:                       # filled by scripts/probe.py — do NOT hand-edit auto fields
      rest_ok: null
      seo_plugin: null           # yoast | rankmath | none
      seo_meta_rest_writable: null
      seo_plugin_emits_graph: null
      uid_roundtrip_ok: null     # idempotency mechanism verified on live site
      html_renders_ok: null      # manual (Task 15 Step 1)
      wpcron_reliable: null       # manual
      default_category_id: null   # manual
      default_author_id: null     # manual
      media_max_bytes: null
      keyword_data: null          # ubersuggest_csv | ai_only
      probed_at: null
```
`courses/trainingint.yaml`:
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
      - { slug: how-to-write-a-professional-email, primary_keyword: how to write a professional email, status: idea }
      - { slug: how-to-write-a-follow-up-email, primary_keyword: how to write a follow up email, status: idea }
      - { slug: how-to-write-a-formal-email-to-your-boss, primary_keyword: how to write a formal email to your boss, status: idea }
      - { slug: how-to-write-an-apology-email-at-work, primary_keyword: how to write an apology email, status: idea }
      - { slug: how-to-write-a-meeting-recap-email, primary_keyword: how to write a meeting recap email, status: idea }
```
- [ ] **Step 4: Run, verify pass** — `python -m pytest tests/test_config.py -v` → PASS.
- [ ] **Step 5: Commit** — `git add config/ courses/ tests/test_config.py && git commit -m "feat: site registry + course spine"`

---

### Task 3: Vendor voice/ + seo/ DATA

**Files:** Create `voice/*.md` (6) + `voice/sync.md`, `seo/*` (5) + `seo/sync.md`, `tests/test_vendored_data.py`

- [ ] **Step 1: Failing test** — `tests/test_vendored_data.py`:
```python
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
V=["voice.md","humor.md","opinions.md","stats.md","stories.md","do-not-write.md"]
S=["checklist.md","link-budget.md","schema-templates.md","audit-budgets.yaml","pillar-map.yaml"]
def test_voice_present():
    for f in V:
        p=ROOT/"voice"/f; assert p.exists() and p.stat().st_size>100, f
    assert "24 years" in (ROOT/"voice/stats.md").read_text(encoding="utf-8")
def test_seo_present():
    for f in S:
        p=ROOT/"seo"/f; assert p.exists() and p.stat().st_size>100, f
    assert "Refuse-to-publish" in (ROOT/"seo/link-budget.md").read_text(encoding="utf-8")
```
- [ ] **Step 2: Run, verify fail** — `python -m pytest tests/test_vendored_data.py -v` → FAIL.
- [ ] **Step 3: Copy verified sources** (audit-confirmed present 2026-05-19):
```bash
cd D:/VP/ARTICLE_ENGINE && mkdir -p voice seo
cp "D:/vp/softskills/1-NEW-SSKILLS/voice/"{voice,humor,opinions,stats,stories,do-not-write}.md voice/
cp "D:/vp/softskills/1-NEW-SSKILLS/seo/"{checklist.md,link-budget.md,schema-templates.md,audit-budgets.yaml,pillar-map.yaml} seo/
```
`voice/sync.md`:
```markdown
# Voice DATA provenance
Vendored 2026-05-19 from D:/vp/softskills/1-NEW-SSKILLS/voice/ (6 files).
softskills' LOCKED voice rules — stats.md facts verbatim, never paraphrased.
Resync = re-copy 6 files; diff before overwrite; softskills is the source of truth.
```
`seo/sync.md`:
```markdown
# SEO DATA provenance
Vendored 2026-05-19 from D:/vp/softskills/1-NEW-SSKILLS/seo/.
link-budget.md is softskills.sg-centric; the trainingint budget is the numeric
block in config/sites.yaml -> sites.trainingint.link_budget, enforced by
scripts/lib/link_budget.py. checklist.md (80 items) used as-is by /ae-6.
pillar-map.yaml is reference topology only; live queue = courses/<site>.yaml.
```
- [ ] **Step 4: Run, verify pass** — `python -m pytest tests/test_vendored_data.py -v` → PASS. If the `"24 years"` assert fails, wrong source copied — re-check the path.
- [ ] **Step 5: Commit** — `git add voice/ seo/ tests/test_vendored_data.py && git commit -m "feat: vendor softskills voice + SEO DATA"`

---

### Task 4: `scripts/lib/ngram.py`

**Files:** Create `scripts/lib/ngram.py`, `tests/test_ngram.py`

- [ ] **Step 1: Failing tests (incl. adversarial + real-calling-convention regression)** — `tests/test_ngram.py`:
```python
from scripts.lib.ngram import shingles, overlap_8gram, voice_survival_ratio
def test_shingles_count():
    assert len(shingles("a b c d e f g h i", 8)) == 2
def test_overlap_detects_shared_phrase():
    a="you should always proofread your email before you hit send today"
    b="experts say you should always proofread your email before you hit send"
    assert any("proofread your email before you hit send" in h for h in overlap_8gram(a,b))
def test_overlap_no_op_implementation_fails():     # ADVERSARIAL: return [] fails this
    t="alpha beta gamma delta epsilon zeta eta theta iota kappa"
    assert overlap_8gram(t,t)
def test_voice_survival():
    v="one two three four five six seven eight nine ten eleven twelve"
    assert voice_survival_ratio(v,v) == 1.0
    assert voice_survival_ratio("completely different words none shared at all here now then",v) < 0.85
def test_voice_survival_html_vs_markdown_not_false_blocked():  # ADVERSARIAL: real call
    # ae-6/ae-8 call voice_survival_ratio(04-seo.html, 03-voice.md): HTML (tags,
    # entities, smart quotes, embedded JSON-LD) vs markdown of the SAME prose must
    # NOT trip the <0.85 gate. A _norm that does not strip markup scores ~0.4 here.
    prose=("Writing a professional email is not hard once you accept that "
           "clarity beats cleverness every single time you sit down to type one")
    md="## Heading\n\n"+prose+"\n\n- a bullet point that is here too\n"
    h=("<h2>Heading</h2><p>"+prose+"</p><ul><li>a bullet point that is here too"
       "</li></ul><script type=\"application/ld+json\">{\"@type\":\"Article\"}</script>")
    assert voice_survival_ratio(h, md) >= 0.85
def test_overlap_dedupes_repeated_match():        # ADVERSARIAL: list (dup) fails this
    rep="copied sentence that appears verbatim in the competitor body text here now"
    art=rep+". filler words in between here. "+rep+"."
    o=overlap_8gram(art, rep)
    assert o and len(o)==len(set(o))
```
- [ ] **Step 2: Run, verify fail** — `python -m pytest tests/test_ngram.py -v` → FAIL.
- [ ] **Step 3: Implement** — `scripts/lib/ngram.py` (v2.1: markup-agnostic tokenization + set-denominator + dedup overlap — see v2.1 fixes note):
```python
import re, html, unicodedata
def _norm(t):
    # Strip HTML tags + decode entities + fold to ascii so the metric compares
    # PROSE not markup: ae-6/ae-8 feed HTML (04-seo.html) vs markdown (03-voice.md),
    # and WordPress emits smart quotes/entities. Plain text is unaffected (no-op).
    t=html.unescape(re.sub(r"<[^>]+>", " ", t))
    t=unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", t.lower())
def shingles(text, n=8):
    w=_norm(text)
    return [tuple(w[i:i+n]) for i in range(len(w)-n+1)] if len(w)>=n else []
def overlap_8gram(a,b,n=8):
    sb={s for s in shingles(b,n)}
    return list(dict.fromkeys(" ".join(s) for s in shingles(a,n) if s in sb))
def voice_survival_ratio(seo_text, voice_text, n=8):
    vs=set(shingles(voice_text,n))           # distinct voice n-grams (denominator)
    if not vs: return 1.0
    se={s for s in shingles(seo_text,n)}
    return sum(1 for s in vs if s in se)/len(vs)
```
- [ ] **Step 4: Run, verify pass** — `python -m pytest tests/test_ngram.py -v` → PASS (6, incl. the HTML-vs-markdown + dedup regression tests that bite the pre-v2.1 impl).
- [ ] **Step 5: Commit** — `git add scripts/lib/ngram.py tests/test_ngram.py && git commit -m "feat: 8-gram overlap + voice-survival (adversarial-tested)"`

---

### Task 5: `scripts/lib/originality.py`

**Files:** Create `scripts/lib/originality.py`, `tests/test_originality.py`

- [ ] **Step 1: Failing tests (incl. adversarial + real-input regression — N2)** — `tests/test_originality.py`:
```python
import pathlib
from scripts.lib.originality import originality_report
ROOT=pathlib.Path(__file__).resolve().parents[1]
STORIES="A trainee once emailed the whole company by mistake. We laughed, then fixed it."
STATS="24 years training in Singapore. 48,000+ working professionals trained."
def test_passes_story_and_stat():
    art=("Real case: A trainee once emailed the whole company by mistake. We "
         "laughed, then fixed it. We have 24 years training in Singapore behind this.")
    r=originality_report(art, STORIES, STATS, ["generic competitor copy about emails"])
    assert r["passes"] and r["count"]>=2
def test_fails_zero_elements():
    art="Generic advice about writing emails that competitors also say."
    r=originality_report(art, STORIES, STATS, [art])
    assert not r["passes"] and r["count"]==0
def test_no_op_pass_stub_fails():     # ADVERSARIAL: {"passes":True} stub fails this
    art="nothing original here at all just filler words repeated repeated"
    r=originality_report(art, STORIES, STATS, [art])
    assert not r["passes"]
def test_real_inputs_html_article():  # ADVERSARIAL: real call site passes 04-seo.html
    stories=(ROOT/"voice/stories.md").read_text(encoding="utf-8")
    stats=(ROOT/"voice/stats.md").read_text(encoding="utf-8")
    html=("<article><h2>Steps</h2><ol>"
          "<li>Define the one outcome the email must achieve</li>"
          "<li>Write the ask in the first two sentences</li>"
          "<li>Cut every sentence that does not serve that ask</li>"
          "</ol><p>Think of a good email like a one-page memo.</p></article>")
    r=originality_report(html, stories, stats,
                         ["totally unrelated competitor prose about kittens here"])
    assert r["checks"]["original_framework"] is True   # HTML <ol> must count (pre-fix: False)
    assert r["checks"]["original_analogy"] is True      # "like a one-page memo"
def test_course_name_alone_does_not_pass(): # ADVERSARIAL: stat needs a digit; "like you" != simile
    stories=(ROOT/"voice/stories.md").read_text(encoding="utf-8")
    stats=(ROOT/"voice/stats.md").read_text(encoding="utf-8")
    art=("Our course Communicate with Confidence helps professionals like you "
         "improve at work and grow in their roles over time consistently here today.")
    r=originality_report(art, stories, stats,
                         ["unrelated competitor text about an entirely different subject"])
    assert r["passes"] is False   # pre-fix: stat(course name)+analogy("like you") => True
```
- [ ] **Step 2: Run, verify fail** — FAIL.
- [ ] **Step 3: Implement** — `scripts/lib/originality.py` (v2.1 N2: HTML-aware framework, numeric-only stat, prose-only story lines, simile-only analogy — see v2.1 fixes note):
```python
import re
from scripts.lib.ngram import overlap_8gram
# YAML key / markdown header / blockquote — not story prose (skip in _has_story)
_KEYISH=re.compile(r"^\s*(#|>|[\w-]+\s*:(\s|$))")
def _story_lines(stories):
    for raw in stories.splitlines():
        ln=raw.strip(" -*")
        if ln and not _KEYISH.match(raw): yield ln
def _has_story(a, stories):
    al=a.lower()
    for ln in _story_lines(stories):
        if len(ln)>30 and ln[:30].lower() in al: return True
    return False
def _has_stat(a, stats):
    al=a.lower()
    for ln in (l.strip(" -*") for l in stats.splitlines()):
        frag=ln.split(".")[0].strip()
        # a real stat is numeric — exclude course names / bio / headers
        if len(frag)>6 and any(ch.isdigit() for ch in frag) and frag.lower() in al:
            return True
    return False
def _has_analogy(a, serp):
    for s in a.replace("\n"," ").split("."):
        sl=s.lower()
        if (re.search(r"\blike (a|an|the) ", sl)
                or any(c in sl for c in ("is like","think of it as","imagine ","as if "))):
            if not any(overlap_8gram(s,b) for b in serp): return True
    return False
def _framework_block(a):
    # article at the real call site is 04-seo.html — count HTML <li> AND markdown
    md=[l for l in a.splitlines() if re.match(r"\s*(\d+\.|\-|\*)\s+\S", l)]
    li=re.findall(r"<li\b[^>]*>(.*?)</li>", a, re.DOTALL|re.IGNORECASE)
    return ("\n".join(md)+"\n"+"\n".join(li)).strip()
def _has_framework(a, serp):
    block=_framework_block(a)
    return bool(block) and not any(overlap_8gram(block,b) for b in serp)
def originality_report(article, stories_md, stats_md, serp_bodies):
    c={"story":_has_story(article,stories_md),"stat":_has_stat(article,stats_md),
       "original_analogy":_has_analogy(article,serp_bodies),
       "original_framework":_has_framework(article,serp_bodies)}
    n=sum(c.values())
    return {"passes": n>=2, "count": n, "checks": c}
```
> **Plan-level decision flagged for owner (C2a, NOT auto-changed):** `_has_story` still uses a verbatim 30-char-prefix match (consistent with voice/sync.md "facts verbatim, never paraphrased"). It will NOT detect a heavily *paraphrased* signature story. Decide whether the originality gate should require near-verbatim signature stories (current) or detect paraphrased retellings (would need fuzzy/8-gram similarity on the story `long:` body). Left as-is pending owner call.
- [ ] **Step 4: Run, verify pass** — PASS (5, incl. the HTML-article + course-name regression tests that bite the pre-v2.1 impl).
- [ ] **Step 5: Commit** — `git add scripts/lib/originality.py tests/test_originality.py && git commit -m "feat: >=2-of-4 originality gate (adversarial-tested)"`

---

### Task 6: `scripts/lib/link_budget.py`

Ported from rules in `D:/vp/softskills/1-NEW-SSKILLS/seo/link-budget.md` (audit-confirmed), parameterised by `config/sites.yaml`.

**Files:** Create `scripts/lib/link_budget.py`, `tests/test_link_budget.py`

- [ ] **Step 1: Failing tests (incl. adversarial)** — `tests/test_link_budget.py`:
```python
from scripts.lib.link_budget import validate_links
B={"internal_sibling_min":2,"internal_sibling_max":3,"primary_course_distinct":1,
   "primary_course_occurrences_max":3,"secondary_course_max":3,
   "authoritative_outbound_min":1,"authoritative_outbound_max":2}
def test_clean_passes():
    inv={"internal_sibling":["/blog/a","/blog/b"],
         "primary_course":["u","u","u"],"secondary_course":["y"],
         "authoritative_outbound":["https://www.skillsfuture.gov.sg/"],
         "anchors":["a1","a2","a3","a4","a5"],"same_paragraph_domains":[]}
    assert validate_links(inv,B)==[]
def test_too_many_primary_occurrences():   # ADVERSARIAL: return [] stub fails
    inv={"internal_sibling":["/a","/b"],"primary_course":["u"]*5,
         "secondary_course":[],"authoritative_outbound":["https://mom.gov.sg"],
         "anchors":["a","b","c","d","e","f","g"],"same_paragraph_domains":[]}
    assert any("primary_course_occurrences" in x for x in validate_links(inv,B))
def test_orphan_and_eeat():
    inv={"internal_sibling":[],"primary_course":["u"],"secondary_course":[],
         "authoritative_outbound":[],"anchors":["x"],"same_paragraph_domains":[]}
    v=validate_links(inv,B)
    assert any("internal_sibling_min" in x for x in v)
    assert any("authoritative_outbound_min" in x for x in v)
def test_dup_anchor_and_spam():
    inv={"internal_sibling":["/a","/b"],"primary_course":["u"],"secondary_course":[],
         "authoritative_outbound":["https://hbr.org"],"anchors":["same","same"],
         "same_paragraph_domains":["trainingint.com"]}
    v=validate_links(inv,B)
    assert any("identical_anchor" in x for x in v)
    assert any("same_paragraph" in x for x in v)
```
- [ ] **Step 2: Run, verify fail** — FAIL.
- [ ] **Step 3: Implement** — `scripts/lib/link_budget.py`:
```python
def validate_links(inv, budget):
    v=[]
    sib=inv["internal_sibling"]
    if len(sib)<budget["internal_sibling_min"]:
        v.append(f"internal_sibling_min: {len(sib)} < {budget['internal_sibling_min']}")
    if len(sib)>budget["internal_sibling_max"]:
        v.append(f"internal_sibling_max: {len(sib)} > {budget['internal_sibling_max']}")
    pc=inv["primary_course"]
    if len(set(pc))>budget["primary_course_distinct"]:
        v.append(f"primary_course_distinct: {len(set(pc))} > {budget['primary_course_distinct']}")
    if len(pc)>budget["primary_course_occurrences_max"]:
        v.append(f"primary_course_occurrences: {len(pc)} > {budget['primary_course_occurrences_max']}")
    if len(inv["secondary_course"])>budget["secondary_course_max"]:
        v.append(f"secondary_course_max: {len(inv['secondary_course'])} > {budget['secondary_course_max']}")
    ao=inv["authoritative_outbound"]
    if len(ao)<budget["authoritative_outbound_min"]:
        v.append(f"authoritative_outbound_min: {len(ao)} < {budget['authoritative_outbound_min']}")
    if len(ao)>budget["authoritative_outbound_max"]:
        v.append(f"authoritative_outbound_max: {len(ao)} > {budget['authoritative_outbound_max']}")
    anchors=[a.strip().lower() for a in inv["anchors"]]
    if len(anchors)!=len(set(anchors)):
        v.append("identical_anchor: two or more anchors identical")
    if any(a in {"click here","learn more","read more","here"} for a in anchors):
        v.append("banned_anchor: generic anchor present")
    if inv["same_paragraph_domains"]:
        v.append(f"same_paragraph: domain repeated in one paragraph ({inv['same_paragraph_domains']})")
    return v
```
- [ ] **Step 4: Run, verify pass** — PASS (4).
- [ ] **Step 5: Commit** — `git add scripts/lib/link_budget.py tests/test_link_budget.py && git commit -m "feat: per-site link-budget validator (adversarial-tested)"`

---

### Task 7: `scripts/lib/jsonld.py` (with real adversarial test — audit M8)

Shapes verified vs `D:/vp/softskills/1-NEW-SSKILLS/seo/schema-templates.md`.

**Files:** Create `scripts/lib/jsonld.py`, `tests/test_jsonld.py`

- [ ] **Step 1: Failing tests (incl. adversarial — a hardcoded-3-node stub must fail)** — `tests/test_jsonld.py`:
```python
import json
from scripts.lib.jsonld import build_jsonld
def _b(**kw):
    base=dict(url="https://t/x/", title="How to X", description="d",
              author="Vinai Prakash", publisher="Intellisoft Training Pte Ltd",
              faqs=[{"q":"Q1?","a":"A1."}],
              breadcrumb=[("Home","https://t/"),("Blog","https://t/blog/"),
                          ("How to X","https://t/x/")])
    base.update(kw); return json.loads(build_jsonld(**base))
def test_three_nodes_and_content():
    g=_b()["@graph"]
    by={n["@type"]:n for n in g}
    assert {"Article","FAQPage","BreadcrumbList"} <= set(by)
    assert by["Article"]["headline"]=="How to X"          # content, not just count
    assert [i["position"] for i in by["BreadcrumbList"]["itemListElement"]]==[1,2,3]
    assert by["FAQPage"]["mainEntity"][0]["name"]=="Q1?"
def test_suppress_skips_node():   # ADVERSARIAL: a stub that ignores suppress fails
    types={n["@type"] for n in _b(suppress={"FAQPage"})["@graph"]}
    assert "FAQPage" not in types and "Article" in types
```
- [ ] **Step 2: Run, verify fail** — FAIL.
- [ ] **Step 3: Implement** — `scripts/lib/jsonld.py`:
```python
import json
def build_jsonld(url,title,description,author,publisher,faqs,breadcrumb,suppress=None):
    suppress=suppress or set(); g=[]
    if "Article" not in suppress:
        g.append({"@type":"Article","headline":title,"description":description,
                  "mainEntityOfPage":url,
                  "author":{"@type":"Person","name":author},
                  "publisher":{"@type":"Organization","name":publisher}})
    if "FAQPage" not in suppress and faqs:
        g.append({"@type":"FAQPage","mainEntity":[
            {"@type":"Question","name":f["q"],
             "acceptedAnswer":{"@type":"Answer","text":f["a"]}} for f in faqs]})
    if "BreadcrumbList" not in suppress and breadcrumb:
        g.append({"@type":"BreadcrumbList","itemListElement":[
            {"@type":"ListItem","position":i+1,"name":n,"item":u}
            for i,(n,u) in enumerate(breadcrumb)]})
    return json.dumps({"@context":"https://schema.org","@graph":g})
```
- [ ] **Step 4: Run, verify pass** — `python -m pytest tests/test_jsonld.py tests/test_scaffold.py -v` → PASS (incl. `test_libs_importable` now green).
- [ ] **Step 5: Commit** — `git add scripts/lib/jsonld.py tests/test_jsonld.py && git commit -m "feat: JSON-LD builder (content + suppress adversarial-tested)"`

---

### Task 8: `scripts/lib/wp_client.py` (uid lookup via `/ae/v1/find` — audit M3)

**Files:** Create `scripts/lib/wp_client.py`, `tests/test_wp_client.py`

- [ ] **Step 1: Failing tests** — `tests/test_wp_client.py`:
```python
import responses
from scripts.lib.wp_client import WPClient
WP="https://www.trainingint.com/wp-json/wp/v2"
AE="https://www.trainingint.com/wp-json/ae/v1"
def c(): return WPClient(WP,"u","p")
@responses.activate
def test_find_uid_returns_id():
    responses.get(f"{AE}/find", json={"id":42}, status=200)
    assert c().find_post_by_uid("abc")==42
@responses.activate
def test_find_uid_404_is_none():
    responses.get(f"{AE}/find", status=404)
    assert c().find_post_by_uid("zzz") is None
@responses.activate
def test_find_slug_none_when_empty():
    responses.get(f"{WP}/posts", json=[], status=200)
    assert c().find_post_by_slug("x") is None
@responses.activate
def test_create_returns_id():
    responses.post(f"{WP}/posts", json={"id":99}, status=201)
    assert c().create_post({"title":"t","status":"draft"})==99
```
- [ ] **Step 2: Run, verify fail** — FAIL.
- [ ] **Step 3: Implement** — `scripts/lib/wp_client.py`:
```python
import requests
from requests.auth import HTTPBasicAuth
UID_META="ae_content_uid"
class WPClient:
    def __init__(self, api_base, user, app_password, timeout=30):
        self.base=api_base.rstrip("/")
        self.ae_base=self.base.replace("/wp/v2","/ae/v1")
        self.auth=HTTPBasicAuth(user, app_password); self.timeout=timeout
    def _get(self,path,**p):
        r=requests.get(f"{self.base}{path}",params=p,auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()
    def me(self): return self._get("/users/me")
    def find_post_by_uid(self, uid):
        r=requests.get(f"{self.ae_base}/find",params={"uid":uid},
                        auth=self.auth,timeout=self.timeout)
        if r.status_code==404: return None
        r.raise_for_status(); return r.json().get("id")
    def find_post_by_slug(self, slug):
        res=self._get("/posts",slug=slug,status="any",per_page=1)
        return res[0]["id"] if res else None
    def create_post(self, payload):
        r=requests.post(f"{self.base}/posts",json=payload,auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()["id"]
    def update_post(self, pid, payload):
        r=requests.post(f"{self.base}/posts/{pid}",json=payload,auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()["id"]
    def upload_media(self, filename, content, mime):
        r=requests.post(f"{self.base}/media",data=content,
            headers={"Content-Disposition":f'attachment; filename="{filename}"',
                     "Content-Type":mime},auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()["id"]
    def read_post_meta(self, pid, key):
        return self._get(f"/posts/{pid}").get("meta",{}).get(key)
    def delete_post(self, pid):
        requests.delete(f"{self.base}/posts/{pid}",params={"force":True},
                        auth=self.auth,timeout=self.timeout)
```
- [ ] **Step 4: Run, verify pass** — PASS (4).
- [ ] **Step 5: Commit** — `git add scripts/lib/wp_client.py tests/test_wp_client.py && git commit -m "feat: WP REST client; uid lookup via /ae/v1/find"`

---

### Task 9: `wp-helper-plugin/ae-helper.php` — ALWAYS installed (audit M3)

Stock WP REST cannot query unregistered meta and silently drops it. This always-installed plugin makes `ae_content_uid` REST-writable and provides a server-side find route (server-side `WP_Query` meta_query *does* work). It also carries the **conditional** SEO-meta-write route used only if the probe finds plugin meta unwritable.

**Files:** Create `wp-helper-plugin/ae-helper.php`, `wp-helper-plugin/README.md`

- [ ] **Step 1: Write the plugin** — `wp-helper-plugin/ae-helper.php`:
```php
<?php
/**
 * Plugin Name: Article Engine Helper
 * Description: Registers ae_content_uid (REST) + /ae/v1/find idempotency route; optional /ae/v1/meta for blocked SEO meta.
 * Version: 1.0.0
 * Requires PHP: 7.4
 */
if (!defined('ABSPATH')) exit;

add_action('init', function () {
    register_post_meta('post', 'ae_content_uid', [
        'show_in_rest'      => true,
        'single'            => true,
        'type'              => 'string',
        'auth_callback'     => function () { return current_user_can('edit_posts'); },
    ]);
});

add_action('rest_api_init', function () {
    register_rest_route('ae/v1', '/find', [
        'methods'  => 'GET',
        'permission_callback' => function () { return current_user_can('edit_posts'); },
        'callback' => function (WP_REST_Request $r) {
            $uid = sanitize_text_field($r->get_param('uid'));
            $q = new WP_Query([
                'post_type'   => 'post',
                'post_status' => 'any',
                'meta_key'    => 'ae_content_uid',
                'meta_value'  => $uid,
                'fields'      => 'ids',
                'posts_per_page' => 1,
            ]);
            if (empty($q->posts)) {
                return new WP_Error('ae_not_found', 'no post for uid', ['status' => 404]);
            }
            return ['id' => (int) $q->posts[0]];
        },
    ]);
    register_rest_route('ae/v1', '/meta/(?P<id>\d+)', [
        'methods'  => 'POST',
        'permission_callback' => function () { return current_user_can('edit_posts'); },
        'callback' => function (WP_REST_Request $r) {
            $id = (int) $r['id'];
            if (get_post_status($id) === false) {
                return new WP_Error('ae_bad', 'bad id', ['status' => 400]);
            }
            foreach (($r->get_json_params()['meta'] ?? []) as $k => $v) {
                update_post_meta($id, sanitize_key($k), wp_kses_post($v));
            }
            return ['ok' => true, 'id' => $id];
        },
    ]);
});
```
`wp-helper-plugin/README.md`: "Zip this folder → trainingint wp-admin → Plugins → Upload Plugin → Activate. Required before Task 10 probe and any /ae-8-publish. The app-password user must have the `edit_posts` capability."
- [ ] **Step 2: Owner installs (prerequisite, not automatable)** — Owner zips `wp-helper-plugin/`, uploads + activates on trainingint.com. Confirm `GET https://www.trainingint.com/wp-json/ae/v1/find?uid=__none__` returns HTTP 404 (route exists, no match) not 404-route-missing — i.e. JSON body `{"code":"ae_not_found"}`.
- [ ] **Step 3: Commit** — `git add wp-helper-plugin/ && git commit -m "feat: always-installed WP helper (uid meta + find route + optional meta route)"`

---

### Task 10: `scripts/probe.py` — P0 design-gating (incl. uid round-trip — audit M3)

**Files:** Create `scripts/probe.py`, `tests/test_probe.py`

- [ ] **Step 1: Failing tests (incl. adversarial)** — `tests/test_probe.py`:
```python
import responses
from scripts.lib.wp_client import WPClient
from scripts.probe import probe_meta_writable, probe_uid_roundtrip
WP="https://www.trainingint.com/wp-json/wp/v2"; AE="https://www.trainingint.com/wp-json/ae/v1"
def wp(): return WPClient(WP,"u","p")
@responses.activate
def test_meta_writable_true_on_match():
    responses.post(f"{WP}/posts", json={"id":7}, status=201)
    responses.post(f"{WP}/posts/7", json={"id":7}, status=200)
    responses.get(f"{WP}/posts/7", json={"id":7,"meta":{"rank_math_title":"TOK"}}, status=200)
    responses.delete(f"{WP}/posts/7", json={}, status=200)
    assert probe_meta_writable(wp(),"rank_math_title","TOK") is True
@responses.activate
def test_meta_writable_false_on_mismatch():   # ADVERSARIAL: hardcoded True fails
    responses.post(f"{WP}/posts", json={"id":8}, status=201)
    responses.post(f"{WP}/posts/8", json={"id":8}, status=200)
    responses.get(f"{WP}/posts/8", json={"id":8,"meta":{"rank_math_title":""}}, status=200)
    responses.delete(f"{WP}/posts/8", json={}, status=200)
    assert probe_meta_writable(wp(),"rank_math_title","TOK") is False
@responses.activate
def test_uid_roundtrip_false_when_find_misses():  # ADVERSARIAL: idempotency must be proven live
    responses.post(f"{WP}/posts", json={"id":9}, status=201)
    responses.get(f"{AE}/find", status=404)        # helper can't find what we just wrote
    responses.delete(f"{WP}/posts/9", json={}, status=200)
    assert probe_uid_roundtrip(wp()) is False
```
- [ ] **Step 2: Run, verify fail** — FAIL.
- [ ] **Step 3: Implement** — `scripts/probe.py`:
```python
"""P0 design-gating preflight. Probes the LIVE site; writes results into
config/sites.yaml. Runtime facts come from the target, never assumed."""
import os, sys, yaml, pathlib, datetime, uuid
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient
ROOT=pathlib.Path(__file__).resolve().parents[1]

def probe_meta_writable(wp, meta_key, token):
    pid=wp.create_post({"title":"AE PROBE del","status":"draft",
                        "content":"<p>x</p>","meta":{meta_key:token}})
    try:
        wp.update_post(pid,{"meta":{meta_key:token}})
        return wp.read_post_meta(pid,meta_key)==token
    finally:
        wp.delete_post(pid)

def probe_uid_roundtrip(wp):
    """Prove the idempotency mechanism on the LIVE site: write ae_content_uid,
    then resolve it back via the helper /ae/v1/find route."""
    tok="probe-"+uuid.uuid4().hex[:10]
    pid=wp.create_post({"title":"AE UID PROBE","status":"draft",
                        "content":"<p>x</p>","meta":{"ae_content_uid":tok}})
    try:
        return wp.find_post_by_uid(tok)==pid
    finally:
        wp.delete_post(pid)

def detect_seo_plugin(wp):
    try:
        s=wp._get("/posts",per_page=1); meta=(s[0].get("meta",{}) if s else {})
        if any(k.startswith("rank_math") for k in meta): return "rankmath"
        if any(k.startswith("_yoast") for k in meta): return "yoast"
    except Exception: pass
    return "none"

def run(site="trainingint"):
    load_dotenv(ROOT/"credentials/.env")
    cfg=yaml.safe_load((ROOT/"config/sites.yaml").read_text())
    s=cfg["sites"][site]
    pw=os.environ.get(s["app_password_env"]); user=os.environ.get(s["app_password_env"]+"_USER")
    if not pw or not user:
        sys.exit(f"Set {s['app_password_env']} and {s['app_password_env']}_USER in credentials/.env")
    wp=WPClient(s["wp_api_base"],user,pw); p=s["probe"]
    try: wp.me(); p["rest_ok"]=True
    except Exception as e: p["rest_ok"]=False; print("REST/auth FAILED:",e)
    if p["rest_ok"]:
        try: p["uid_roundtrip_ok"]=probe_uid_roundtrip(wp)
        except Exception as e: p["uid_roundtrip_ok"]=False; print("UID roundtrip FAILED (helper plugin installed?):",e)
        plugin=detect_seo_plugin(wp); p["seo_plugin"]=plugin
        mk={"rankmath":"rank_math_title","yoast":"_yoast_wpseo_title"}.get(plugin)
        p["seo_meta_rest_writable"]=probe_meta_writable(wp,mk,"AE-PROBE-TOK") if mk else False
    p["probed_at"]=datetime.date.today().isoformat()
    (ROOT/"config/sites.yaml").write_text(yaml.safe_dump(cfg,sort_keys=False))
    print("PROBE:",yaml.safe_dump(p,sort_keys=False))
    print("\nMANUAL items to fill in config/sites.yaml before first batch:")
    print(" html_renders_ok, wpcron_reliable, default_category_id,")
    print(" default_author_id, keyword_data (ubersuggest_csv|ai_only)")

if __name__=="__main__":
    run(sys.argv[1] if len(sys.argv)>1 else "trainingint")
```
- [ ] **Step 4: Run, verify pass** — `python -m pytest tests/test_probe.py -v` → PASS (3, incl. both adversarial).
- [ ] **Step 5: Commit** — `git add scripts/probe.py tests/test_probe.py && git commit -m "feat: P0 probe incl. live uid-roundtrip (adversarial-tested)"`
- [ ] **Step 6: Owner live run (prerequisite — not automatable)** — Owner creates a WP application password (trainingint wp-admin → Users → Profile → Application Passwords; the user must have `edit_posts`), Task 9 plugin already active, then `credentials/.env`:
```
WP_TRAININGINT=xxxx xxxx xxxx xxxx
WP_TRAININGINT_USER=vinai
```
Run `python scripts/probe.py trainingint`. **HARD GATE:** do not start Task 11's live use or any `/ae-8-publish` unless `rest_ok: true` AND `uid_roundtrip_ok: true` (idempotency real on this site) AND `seo_meta_rest_writable` is non-null. If `seo_meta_rest_writable: false`, publishing must route SEO meta through `/ae/v1/meta` (already in the Task 9 plugin; wired in Task 11).

---

### Task 11: `scripts/wp_publish.py` — idempotent publisher + media + internal links (audit M3/M4)

**Files:** Create `scripts/wp_publish.py`, `tests/test_wp_publish.py`

- [ ] **Step 1: Failing tests — duplicate-post + media + link-resolution + helper-meta** — `tests/test_wp_publish.py`:
```python
import responses
from scripts.lib.wp_client import WPClient
from scripts.wp_publish import publish_article, content_uid, resolve_internal_links, push_meta_via_helper, resolve_inline_media
WP="https://www.trainingint.com/wp-json/wp/v2"; AE="https://www.trainingint.com/wp-json/ae/v1"
def wp(): return WPClient(WP,"u","p")

@responses.activate
def test_first_publish_creates_scheduled():
    responses.get(f"{AE}/find", status=404)            # uid not found
    responses.get(f"{WP}/posts", json=[], status=200)  # slug not found
    cr=responses.post(f"{WP}/posts", json={"id":100}, status=201)
    pid=publish_article(wp(),"uid1","how-to-x","How to X","<p>b</p>",{},
                        "2026-06-01T09:00:00",5,1)
    assert pid==100 and cr.call_count==1
    body=responses.calls[-1].request.body
    assert b'"future"' in body and b"2026-06-01T09:00:00" in body

@responses.activate
def test_rerun_same_uid_updates_not_duplicates():     # ADVERSARIAL: always-create stub fails
    responses.get(f"{AE}/find", json={"id":100}, status=200)   # uid FOUND
    cr=responses.post(f"{WP}/posts", json={"id":999}, status=201)
    up=responses.post(f"{WP}/posts/100", json={"id":100}, status=200)
    pid=publish_article(wp(),"uid1","how-to-x","How to X","<p>b</p>",{},
                        "2026-06-01T09:00:00",5,1)
    assert pid==100 and cr.call_count==0 and up.call_count==1

def test_resolve_internal_links_in_batch_vs_unresolved():
    html='See <a href="ae:sibling:how-to-y">Y</a> and <a href="ae:sibling:how-to-z">Z</a>.'
    status={"how-to-y":{"url":"https://www.trainingint.com/blog/how-to-y/"}}
    out,unresolved=resolve_internal_links(html,status)
    assert "https://www.trainingint.com/blog/how-to-y/" in out
    assert "ae:sibling:how-to-y" not in out
    assert "how-to-z" in unresolved and 'href="ae:sibling:how-to-z"' not in out  # left as plain text

@responses.activate
def test_push_meta_via_helper():
    h=responses.post(f"{AE}/meta/100", json={"ok":True,"id":100}, status=200)
    push_meta_via_helper(wp(),100,{"rank_math_title":"T"})
    assert h.call_count==1

@responses.activate
def test_resolve_inline_media_uploads_and_rewrites(tmp_path):  # spec §8.2 inline imgs
    (tmp_path/"hero.jpg").write_bytes(b"\xff\xd8jpeg")
    responses.post(f"{WP}/media", json={"id":55,
        "source_url":"https://www.trainingint.com/wp-content/uploads/hero.jpg"}, status=201)
    out=resolve_inline_media(wp(),
        '<img src="ae:img:hero.jpg" alt="x"> and <img src="ae:img:hero.jpg">',
        str(tmp_path))
    assert out.count("https://www.trainingint.com/wp-content/uploads/hero.jpg")==2
    assert "ae:img:" not in out

@responses.activate
def test_tags_included_when_passed():                          # spec §8.3 tags
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[], status=200)
    responses.post(f"{WP}/posts", json={"id":101}, status=201)
    publish_article(wp(),"u","s","T","<p>b</p>",{},
                     "2026-06-01T09:00:00",5,1, tags=[3,4])
    assert b'"tags"' in responses.calls[-1].request.body
```
- [ ] **Step 2: Run, verify fail** — FAIL.
- [ ] **Step 3: Implement** — `scripts/wp_publish.py`:
```python
"""Idempotent scheduled-post publisher. find_post_by_uid hits the always-installed
helper route (Task 9), so a rerun never duplicates a post — verified live by
probe_uid_roundtrip (Task 10) before this is used."""
import re, hashlib, mimetypes, pathlib, requests

def content_uid(site, slug):
    return hashlib.sha1(f"{site}:{slug}".encode()).hexdigest()[:16]

def resolve_internal_links(html, status_map):
    """Replace ae:sibling:<slug> hrefs with live URLs for siblings present in
    status_map; for siblings not yet live, strip the anchor to plain text and
    report them (NO autonomous edits to other posts — spec §8)."""
    unresolved=[]
    def repl(m):
        slug=m.group(1)
        info=status_map.get(slug)
        if info and info.get("url"):
            return f'href="{info["url"]}"'
        unresolved.append(slug)
        return 'data-ae-unresolved="1"'
    html=re.sub(r'href="ae:sibling:([^"]+)"', repl, html)
    # turn any anchor we could not resolve into plain text (drop the <a> wrapper)
    for slug in set(unresolved):
        html=re.sub(r'<a [^>]*data-ae-unresolved="1"[^>]*>(.*?)</a>', r'\1', html, count=1)
    return html, unresolved

def upload_featured(wp, image_path):
    p=pathlib.Path(image_path)
    mime=mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return wp.upload_media(p.name, p.read_bytes(), mime)

def push_meta_via_helper(wp, post_id, meta):
    r=requests.post(f"{wp.ae_base}/meta/{post_id}", json={"meta":meta},
                    auth=wp.auth, timeout=wp.timeout)
    r.raise_for_status()

def resolve_inline_media(wp, html, images_dir):
    """Upload each `ae:img:<filename>` placeholder's local file from images_dir
    and rewrite its src to the live WP media source_url (spec §8.2 — inline
    images, not just the hero). Mirrors the ae:sibling: resolve pattern; uploads
    each distinct file once. Direct media POST (wp.upload_media returns the id,
    but an inline <img src> needs the URL)."""
    cache={}
    def repl(m):
        fn=m.group(1)
        if fn not in cache:
            p=pathlib.Path(images_dir)/fn
            mime=mimetypes.guess_type(p.name)[0] or "image/jpeg"
            r=requests.post(f"{wp.base}/media", data=p.read_bytes(),
                headers={"Content-Disposition":f'attachment; filename="{p.name}"',
                         "Content-Type":mime}, auth=wp.auth, timeout=wp.timeout)
            r.raise_for_status(); cache[fn]=r.json()["source_url"]
        return f'src="{cache[fn]}"'
    return re.sub(r'src="ae:img:([^"]+)"', repl, html)

def publish_article(wp, uid, slug, title, html, meta, scheduled_iso,
                    category_id, author_id, featured_path=None,
                    status_map=None, seo_meta_rest_writable=True,
                    tags=None, images_dir=None):
    if status_map is not None:
        html, _ = resolve_internal_links(html, status_map)
    if images_dir is not None:
        html = resolve_inline_media(wp, html, images_dir)
    payload={"title":title,"slug":slug,"content":html,"status":"future",
             "date":scheduled_iso,"categories":[category_id],"author":author_id,
             "meta":{**({} if not seo_meta_rest_writable else meta),
                     "ae_content_uid":uid}}
    if tags:
        payload["tags"]=tags
    if featured_path:
        payload["featured_media"]=upload_featured(wp, featured_path)
    existing=wp.find_post_by_uid(uid) or wp.find_post_by_slug(slug)
    pid=wp.update_post(existing,payload) if existing is not None else wp.create_post(payload)
    if not seo_meta_rest_writable and meta:
        push_meta_via_helper(wp, pid, meta)
    return pid
```
- [ ] **Step 4: Run, verify pass** — `python -m pytest tests/test_wp_publish.py -v` → PASS (6, incl. duplicate-post + link-resolution + inline-media + tags + helper-meta).
- [ ] **Step 5: Commit** — `git add scripts/wp_publish.py tests/test_wp_publish.py && git commit -m "feat: idempotent publisher + media + internal-link resolution (adversarial-tested)"`

---

### Task 12: Port `ae-1`…`ae-4` (deterministic transforms — audit B1)

**Files:** Create `.claude/commands/ae-{1,2,3,4}-*.md`

- [ ] **Step 1: Copy verified sources**
```bash
cd D:/VP/ARTICLE_ENGINE && mkdir -p .claude/commands
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-1-keyword-research.md" .claude/commands/ae-1-keyword-research.md
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-2-serp-analyze.md"     .claude/commands/ae-2-serp-analyze.md
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-3-draft.md"            .claude/commands/ae-3-draft.md
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-4-voice-pass.md"       .claude/commands/ae-4-voice-pass.md
```
- [ ] **Step 2: Apply DETERMINISTic transforms to all four** (sed; order matters):
```bash
cd D:/VP/ARTICLE_ENGINE/.claude/commands
for f in ae-1-keyword-research.md ae-2-serp-analyze.md ae-3-draft.md ae-4-voice-pass.md; do
  sed -i \
    -e 's#src/content/blog/\$ARGUMENTS#content/trainingint/$ARGUMENTS#g' \
    -e 's#seo/pillar-map\.yaml#courses/trainingint.yaml#g' \
    -e 's#pillar-map\.yaml#courses/trainingint.yaml#g' \
    -e 's#softskills\.sg blog pipeline#Article Engine pipeline (trainingint.com)#g' \
    -e 's#softskills\.sg#trainingint.com#g' \
    -e '/how-to-speak-confidently-in-meetings/d' \
    -e '/[Cc]anonical fixture/d' \
    -e '/[Cc]anonical reference/d' \
    -e '/K1 fixture/d' \
    -e 's#docs/superpowers/specs/2026-04-30-softskills-blog-seo-pipeline-design\.md#docs/superpowers/specs/2026-05-19-article-engine-design.md#g' \
    "$f"
done
# ae-2: append the serp-bodies output requirement (gate input for /ae-6)
printf '\n\n## Additional output (Article Engine)\nAlso write `content/trainingint/$ARGUMENTS/_research/serp-bodies/{1,2,3}.txt` — the full extracted body text of the top-3 results. Required input for the /ae-6 originality + n-gram gates.\n' >> ae-2-serp-analyze.md
```
- [ ] **Step 3: Verify (aligned to what the transforms actually produce)**
```bash
cd D:/VP/ARTICLE_ENGINE/.claude/commands
! grep -li "softskills\|how-to-speak-confidently\|pillar-map\.yaml\|src/content/blog\|2026-04-30-softskills" ae-{1,2,3,4}-*.md && \
grep -q "serp-bodies" ae-2-serp-analyze.md && \
grep -q "Article Engine pipeline (trainingint.com)" ae-1-keyword-research.md && echo "ae-1..4 OK"
```
Expected: prints `ae-1..4 OK` (the leading `!` makes the first grep succeed only if NOTHING matches — i.e. every softskills/fixture/old-path string is gone).
- [ ] **Step 4: Commit** — `git add .claude/commands/ae-{1,2,3,4}-*.md && git commit -m "feat: port ae-1..4 (deterministic WP transforms)"`

---

### Task 13: Port `ae-6-seo-pass` (real source strings + trainingint links — audit B2/M6)

**Files:** Create `.claude/commands/ae-6-seo-pass.md`

- [ ] **Step 1: Copy verified source**
```bash
cp "D:/vp/softskills/1-NEW-SSKILLS/.claude/commands/blog-6-seo-pass.md" \
   D:/VP/ARTICLE_ENGINE/.claude/commands/ae-6-seo-pass.md
```
- [ ] **Step 2: Apply transforms (target strings verified present in blog-6 2026-05-19)**
```bash
cd D:/VP/ARTICLE_ENGINE/.claude/commands
sed -i \
  -e 's#src/content/blog/\$ARGUMENTS#content/trainingint/$ARGUMENTS#g' \
  -e 's#softskills\.sg blog pipeline#Article Engine pipeline (trainingint.com)#g' \
  -e 's#softskills\.sg#trainingint.com#g' \
  -e 's#softskills_sg#trainingint#g' \
  -e 's#04-seo\.md#04-seo.html#g' \
  -e '/how-to-speak-confidently-in-meetings/d' \
  -e '/[Cc]anonical fixture/d' \
  -e 's#docs/superpowers/specs/2026-04-30-softskills-blog-seo-pipeline-design\.md#docs/superpowers/specs/2026-05-19-article-engine-design.md#g' \
  ae-6-seo-pass.md
```
Then make these explicit content replacements (the literal source lines exist — verified):
- Replace the line containing `these become FAQPage JSON-LD via \`BlogLayout\`` with: `  - \`faqs\` array filled (4–8 Q&A — these become FAQPage JSON-LD built by scripts.lib.jsonld)`
- Replace the bullet starting `- **Schema is auto-emitted** by \`BlogLayout\`` (through `...those generators consume.`) with:
  `- **Schema:** build JSON-LD via \`python -c "from scripts.lib.jsonld import build_jsonld; ..."\`; pass \`suppress={'FAQPage','BreadcrumbList'}\` for any type the active SEO plugin already emits (config/sites.yaml probe.seo_plugin_emits_graph). Embed the returned \`<script type="application/ld+json">\` block at the end of the HTML body.`
- Replace the **Internal link insertions** + **External link insertions** sub-section (the lines specifying "3–5 internal trainingint.com blog links", "1–2 internal trainingint.com course/category links", "≤3 trainingint.com links", "≤1 intellisoft.com.sg link" — note the global `softskills.sg→trainingint.com` already mangled these) with the trainingint budget verbatim:
  ```
  - **Internal links (trainingint.com siblings):** 2–3 links to sibling blog posts in the same course cluster. Use `href="ae:sibling:<slug>"` placeholders — scripts/wp_publish.py resolves these to live URLs at publish (unresolved siblings are dropped to plain text, never linked broken).
  - **Course links:** exactly 1 primary course (the cluster's `course_url`) as an above-fold CTA + a bottom CTA + at most 1 contextual body link (same URL ≤3×). 2–3 secondary courses (from courses/trainingint.yaml `secondary_courses`) as contextual links.
  - **Authoritative outbound:** 1–2 (SSG, MOM, HBR, peer-reviewed), `target="_blank" rel="noopener"`, never `rel="sponsored"`.
  ```
- Replace the VOICE-DAMAGE manual instruction with: `Compute programmatically: python -c "from scripts.lib.ngram import voice_survival_ratio as v; print(v(open('content/trainingint/$ARGUMENTS/_draft/04-seo.html',encoding='utf-8').read(), open('content/trainingint/$ARGUMENTS/_draft/03-voice.md',encoding='utf-8').read()))". If < 0.85, STOP, show the diff, do not write 04-seo.html.`
- Replace the `src/lib/link-budget.ts` / `npx tsx` validator block with: `Build the link inventory dict and run scripts.lib.link_budget.validate_links(inv, budget) where budget = config/sites.yaml sites.trainingint.link_budget. If it returns any violations, fix and revalidate before writing 04-seo.html.`
- Replace the originality-gate prose with: `Run scripts.lib.originality.originality_report(article, open('voice/stories.md').read(), open('voice/stats.md').read(), [open(f).read() for f in glob('content/trainingint/$ARGUMENTS/_research/serp-bodies/*.txt')]). If passes is False, surface to the user — do not paper over.`
- Add an **Inline images** instruction (replaces the Astro-component image model, which does not survive to WP): reference every inline image as `<img src="ae:img:<filename>" alt="<descriptive alt>">` where `<filename>` is the file in `content/trainingint/$ARGUMENTS/images/` (hero stays the featured image, set at publish). This mirrors the `ae:sibling:` placeholder — scripts/wp_publish.py uploads each referenced image to WP media and rewrites the src to the live URL at publish (spec §8.2). Never emit a raw local path or an un-prefixed remote Pexels URL in the body.
- [ ] **Step 3: Verify**
```bash
cd D:/VP/ARTICLE_ENGINE/.claude/commands
grep -q "voice_survival_ratio" ae-6-seo-pass.md && \
grep -q "originality_report" ae-6-seo-pass.md && \
grep -q "build_jsonld" ae-6-seo-pass.md && \
grep -q "ae:sibling:" ae-6-seo-pass.md && \
grep -q "ae:img:" ae-6-seo-pass.md && \
grep -q "04-seo.html" ae-6-seo-pass.md && \
! grep -qi "npx tsx\|auto-emitted\|softskills\|04-seo\.md\b\|BlogLayout" ae-6-seo-pass.md && echo "ae-6 OK"
```
Expected: prints `ae-6 OK` (confirms TS validator, BlogLayout, softskills refs, .md output all gone; Python gates + sibling placeholders + HTML output present).
- [ ] **Step 4: Commit** — `git add .claude/commands/ae-6-seo-pass.md && git commit -m "feat: port ae-6 (Python gates, trainingint link budget, real-string transforms)"`

---

### Task 14: `ae-8-publish.md` + `ae-batch.md` (null-probe-field hard gate — audit M5)

**Files:** Create `.claude/commands/ae-8-publish.md`, `.claude/commands/ae-batch.md`

- [ ] **Step 1: Write `ae-8-publish.md`**
```markdown
---
description: Stage 8 — push a reviewed slug to WordPress as a future-dated scheduled post. Strict gates. Idempotent (no duplicate on rerun).
argument-hint: <slug> [--override]
---

# /ae-8-publish

Stage 8 for `$ARGUMENTS` on trainingint.com.
**Spec:** docs/superpowers/specs/2026-05-19-article-engine-design.md §8

## PRE-FLIGHT GATES (refuse if any fail; only --override bypasses cadence)
1. **Probe gate (HARD):** from config/sites.yaml sites.trainingint.probe, REFUSE unless
   ALL of: rest_ok==true, uid_roundtrip_ok==true, seo_meta_rest_writable is not null,
   default_category_id is not null, default_author_id is not null,
   seo_plugin_emits_graph is not null,
   html_renders_ok==true, wpcron_reliable==true, keyword_data is not null.
   (A null here means P0/Task 15 Step 1 is incomplete — do not publish blind.)
2. **Cadence guard:** count status/trainingint.yaml entries with scheduled_date in the
   last 7 days; if > cadence.per_week (5), REFUSE unless --override.
3. **Voice-damage:** scripts.lib.ngram.voice_survival_ratio(04-seo.html, 03-voice.md) ≥ 0.85.
4. **Originality:** scripts.lib.originality.originality_report(...).passes is True.
5. **Anti-plagiarism:** scripts.lib.ngram.overlap_8gram(article, each _research/serp-bodies/*.txt)
   is empty; else REFUSE naming the phrase.
6. **Link budget:** scripts.lib.link_budget.validate_links(inv, budget) == [].
7. **Course registration:** $ARGUMENTS exists in courses/trainingint.yaml with matching
   primary_keyword and a course_url; else REFUSE.

## Publish (single idempotent call)
scheduled_iso = next free weekday 09:00 slot from status/trainingint.yaml (5/wk Mon–Fri).
Run python that: loads config + credentials/.env, builds WPClient, reads 04-seo.html,
then calls scripts.wp_publish.publish_article(wp, content_uid('trainingint',slug), slug,
title, html, seo_meta, scheduled_iso, probe.default_category_id, probe.default_author_id,
featured_path=<hero image>, status_map=<status/trainingint.yaml>,
seo_meta_rest_writable=probe.seo_meta_rest_writable,
tags=<keyword-derived tag ids/names, or omit>,
images_dir=content/trainingint/<slug>/images/ ). Idempotent: rerun UPDATES, never
duplicates (helper /ae/v1/find + adversarial-tested in scripts/wp_publish.py).
Inline `ae:img:<file>` placeholders + the hero are uploaded to WP media and rewritten
to live URLs (spec §8.2); `tags` set alongside category/author (spec §8.3).

## After publish
Update status/trainingint.yaml: slug → {status: scheduled, scheduled_date, wp_post_id}.
Surface: post id, scheduled date, wp-admin edit URL
(https://www.trainingint.com/wp-admin/post.php?post=<id>&action=edit), and any
unresolved sibling links returned (they were dropped to plain text — they re-link
naturally when the sibling publishes and that article is regenerated/edited).

## Refuse if any gate fails — say which gate and the exact failure.
```
- [ ] **Step 2: Write `ae-batch.md`**
```markdown
---
description: Drive 5–15 slugs through ae-1..ae-4, stop at the human review gate.
argument-hint: <course-id | comma-separated slugs>
---

# /ae-batch

Batch for `$ARGUMENTS` on trainingint.com.

## Process
1. Resolve slugs: if a course id, take that course's `status: idea` slugs from
   courses/trainingint.yaml (SKIP `status: proposed` — quarantined per spec §6). Cap 15.
2. Per slug in order: /ae-1 → /ae-2 → /ae-3 → /ae-4. Parallel sub-agents per slug
   where independent (softskills pattern). Each stage writes its artifact before next; resumable.
3. **STOP at the human review gate.** Print a table: slug | title | primary_keyword |
   content/trainingint/<slug>/_draft/03-voice.md. Tell the owner: edit each 03-voice.md;
   then per accepted slug run /ae-6-seo-pass <slug> then /ae-8-publish <slug>.
4. Do NOT run /ae-6 or /ae-8 automatically — those are post-review.

## Warn (don't block research) if config/sites.yaml probe.rest_ok != true:
publishing is blocked until scripts/probe.py passes; research/draft may still proceed.
```
- [ ] **Step 3: Verify**
```bash
cd D:/VP/ARTICLE_ENGINE/.claude/commands
grep -q "uid_roundtrip_ok==true" ae-8-publish.md && \
grep -q "default_category_id is not null" ae-8-publish.md && \
grep -q "status: proposed" ae-batch.md && \
! grep -qi "lighthouse\|coolify\|index.mdx\|npm run build\|GSC indexing" ae-8-publish.md && \
echo "ae-8 + ae-batch OK"
```
Expected: prints `ae-8 + ae-batch OK`.
- [ ] **Step 4: Commit** — `git add .claude/commands/ae-8-publish.md .claude/commands/ae-batch.md && git commit -m "feat: ae-8 (full probe gate) + ae-batch driver"`

---

### Task 15: First real batch end-to-end (P4, owner-driven)

- [ ] **Step 1:** Owner fills the manual probe fields in `config/sites.yaml` after a render check: run `/ae-8-publish` on ONE throwaway slug, open the wp-admin edit URL + front-end preview, confirm HTML + JSON-LD render. Set `html_renders_ok`, `wpcron_reliable` (confirm a real cron hits `wp-cron.php` or install "Missed Scheduled Posts Publisher"), `default_category_id`, `default_author_id`, `keyword_data`, and `seo_plugin_emits_graph` (inspect the rendered preview page source: true if the active SEO plugin already injects its own `application/ld+json` `@graph` — ae-6 then suppresses those types to avoid duplicate schema, spec §8.4/§9.3). If `html_renders_ok` is false → STOP, escalate (body-format branch, spec §9.4).
- [ ] **Step 2:** `/ae-batch writing-professional-emails` → 5 drafts to `_draft/03-voice.md`, stops at review gate.
- [ ] **Step 3:** Owner does a **genuine edit pass** on each `03-voice.md` (D3 — the real scaled-content-abuse defence; not optional).
- [ ] **Step 4:** Per accepted slug: `/ae-6-seo-pass <slug>` then `/ae-8-publish <slug>`. Confirm `status/trainingint.yaml` shows each `scheduled` with a distinct weekday date + `wp_post_id`.
- [ ] **Step 5:** On the first scheduled date, confirm the post auto-published (front-end URL live). If it "missed schedule", `wpcron_reliable` was wrong — install the missed-schedule guard and re-confirm.
- [ ] **Step 6:** `git add content/ status/ && git commit -m "content: first trainingint batch (writing-professional-emails)"`

---

### Task 16: Multi-site proof (P5, owner-driven)

- [ ] **Step 1:** Add a second site block to `config/sites.yaml` (e.g. `intellisoft`) with `wp_api_base`, `ae_api_base`, `app_password_env`, `link_budget`, empty `probe`.
- [ ] **Step 2:** Create `courses/intellisoft.yaml` (same shape as trainingint).
- [ ] **Step 3:** Owner installs the Task 9 helper plugin on that site, creates its WP app password, runs `python scripts/probe.py intellisoft`, fills manual probe fields.
- [ ] **Step 4:** `grep -rn "trainingint" .claude/commands/` — confirm only example text, not logic, is site-specific. Run `/ae-batch <course-id>` for that site → review → `/ae-6` → `/ae-8-publish`. **Gate:** zero code changes were needed to onboard the second site.
- [ ] **Step 5:** `git commit -m "feat: multi-site proof (second site via config + helper only)"`

---

## Self-Review (grounded in steps, not task names — per obs #59)

**1. Spec coverage (cite implementing step):**
- §3 reuse → Tasks 3/12/13 copy only audit-verified sources; transform strings verified against real files.
- §5 topology → Tasks 1–14 create exactly the spec file tree (incl. `wp-helper-plugin/`).
- §6 cluster + quarantine → Task 2 `status: idea/proposed`; Task 14 `ae-batch.md` Step "SKIP `status: proposed`".
- §7 stages → Task 12 (ae-1..4), Task 13 (ae-6), Task 14 (ae-8/ae-batch).
- §7.1 gates → originality Task 5, n-gram/voice-damage Task 4, link-budget Task 6, all wired in Task 13 Step 2 and gated in Task 14 ae-8 gates 3–6; each has a named adversarial test (traced below).
- §8.1 idempotent create → Task 11 `publish_article` `existing=find_post_by_uid or find_post_by_slug`; **made real on stock WP** by Task 9 plugin (registered meta + `/ae/v1/find`) and proven live by Task 10 `probe_uid_roundtrip` (gated in Task 14 gate 1).
- §8.2 media (hero + **inline**) → Task 11 `upload_featured` + `payload["featured_media"]` (hero) and `resolve_inline_media` (every `ae:img:` placeholder → uploaded WP media URL), tests `test_first_publish_creates_scheduled` + `test_resolve_inline_media_uploads_and_rewrites`; `upload_media` in Task 8. ae-6 emits `ae:img:` placeholders (Task 13 Step 2); ae-8 passes `images_dir` (Task 14).
- §8.3 categories/tags/author → Task 11 payload always sets `categories`+`author`; `tags` when provided (`test_tags_included_when_passed`); ae-8 passes `tags` (Task 14).
- §8.5 internal-link resolution (404 lesson, no silent live edits) → Task 11 `resolve_internal_links` + test `test_resolve_internal_links_in_batch_vs_unresolved`; unresolved siblings become plain text, never broken links, never edits to other posts.
- §8.4 SEO meta + helper branch → Task 9 conditional `/ae/v1/meta`; Task 11 `push_meta_via_helper` when `seo_meta_rest_writable` false; test `test_push_meta_via_helper`.
- §9 probe (rest, plugin, meta-writable, uid-roundtrip, manual render/wpcron/ids/emits-graph) → Task 10 + Task 15 Step 1 manual fill (incl. `seo_plugin_emits_graph`, spec §9.3 — feeds ae-6 `suppress=`); gated in Task 14 gate 1 (ALL fields incl. nulls — fixes audit M5 + the dead-suppress gap).
- §10 voice/SEO DATA + sync.md → Task 3.
- §12 phases P0–P5 → Tasks 1–16.
No spec requirement is matched to a task name only; each maps to a concrete step/function/test above.

**2. Placeholder scan:** none. Owner-driven runbook Tasks 15–16 are live-site by nature and say so with concrete commands. Conditional SEO-meta route lives in the always-installed Task 9 plugin (no separate conditional task to skip).

**3. Type consistency:** `WPClient` methods (Task 8: `me/find_post_by_uid/find_post_by_slug/create_post/update_post/upload_media/read_post_meta/delete_post`, attr `ae_base`) match every caller (Tasks 10, 11). `publish_article(wp,uid,slug,title,html,meta,scheduled_iso,category_id,author_id,featured_path=None,status_map=None,seo_meta_rest_writable=True,tags=None,images_dir=None)` matches its tests and the Task 14 ae-8 call (new kwargs are trailing+optional — existing positional callers/tests unaffected). `resolve_internal_links`/`resolve_inline_media`/`upload_featured`/`push_meta_via_helper`/`content_uid` consistent across Task 11 def + tests + ae-8. `ae_content_uid` string identical in Task 9 PHP, Task 8/10/11 Python.

**4. Adversarial-test trace (each named test vs a trivial stub):**
- ngram `test_overlap_no_op_implementation_fails`: stub `return []` → `assert overlap_8gram(t,t)` fails. ✅ bites.
- ngram voice half: stub `return 1.0` → `< 0.85` assert fails. ✅
- ngram `test_voice_survival_html_vs_markdown_not_false_blocked`: the pre-v2.1 non-stripping `_norm` scores ~0.4 on identical prose in HTML-vs-md → `>= 0.85` fails. ✅ bites the original plan code (the defect the quality gate caught).
- ngram `test_overlap_dedupes_repeated_match`: list-returning (dup) overlap → `len(o)==len(set(o))` fails. ✅
- originality `test_no_op_pass_stub_fails`: stub `{"passes":True}` → `assert not r["passes"]` fails. ✅
- originality `test_real_inputs_html_article`: pre-v2.1 `_has_framework` returns False on HTML `<ol>` → `assert checks["original_framework"] is True` fails. ✅ bites the original plan code (the N2 defect the quality gate caught).
- originality `test_course_name_alone_does_not_pass`: pre-v2.1 stat matches a non-numeric course name + analogy fires on "like you" → `passes` True → `assert passes is False` fails. ✅
- link_budget `test_too_many_primary_occurrences`: stub `return []` → `any("primary_course_occurrences"...)` fails. ✅
- jsonld `test_suppress_skips_node`: stub ignoring `suppress` still emits FAQPage → `assert "FAQPage" not in types` fails (M8 fixed — was weak). ✅
- probe `test_meta_writable_false_on_mismatch` + `test_uid_roundtrip_false_when_find_misses`: hardcoded-True stubs fail (readback/​find mismatch). ✅
- wp_publish `test_rerun_same_uid_updates_not_duplicates`: always-create stub → `cr.call_count==0` fails. ✅ And this is now *semantically* real (not just mock-true) because Task 9 registers the meta + find route and Task 10 proves the round-trip live before Task 11 is used.
Runtime facts (REST/meta/uid-roundtrip/render/wpcron/category-author ids) all come from Task 10 live probe + Task 15 Step 1, gated in Task 14 gate 1; none assumed.
