# Legacy Nightly Improvement + Independent SEO Audit — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each night, adopt + improve 3 legacy WordPress posts (safely, without regressing their SEO meta or TOC), run an independent SEO audit on each improvement, surface issues + a prepared fix in the review dashboard, and let Vinai approve → fix → republish.

**Architecture:** Extends the existing `AE-NightlyImprove` job (`nightly_improve.ps1`) — NOT a new cron. Phase 2A fixes the two `adopt_legacy` blockers found by the 2026-06-10 republish gate (meta-blanking, TOC junk) so legacy republish is safe, then adds a "legacy trickle" phase (adopt 3 untracked + improve exactly those 3). Phase 2B adds a post-improvement audit (`audit_artifact_html` deterministic gate → `claude-seo:seo-page` on flagged), writes a per-article audit+fix record, and surfaces it in the AE review dashboard (:5001) and the existing PKM dashboard AE card (:5000).

**Tech Stack:** Python 3, pytest 8, `responses` (HTTP mock), PyYAML, Flask 3, PowerShell 5.1 (the nightly), `claude -p` headless skill invocation.

**Decisions locked (2026-06-10 brainstorm):** one job (extend AE-NightlyImprove); trickle adoption 3/night; audit = `audit_live.audit_artifact_html` deterministic gate on every article, escalate flagged articles to `claude-seo:seo-page`; fix model = surface issues + prepared fix, apply + republish on Vinai's approval; review in AE dashboard (:5001) with a card in PKM dashboard (:5000).

**Conventions observed (do not deviate):**
- Artifact format: `"---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=True) + "---\n" + body`. Frontmatter split on `"\n---\n"`.
- `status/<site>.yaml` written with `yaml.dump(data, allow_unicode=True, sort_keys=True)`.
- HTTP mocked with `responses`; pure logic tested against `tmp_path`; import as `from scripts import x` / `from scripts.lib import y` (repo root on sys.path via `tests/conftest.py`).
- Audit check dict shape (from `scripts/audit_live.py`): `{"check": str, "ok": bool, "detail": str, "severity": "error"|"info"}`.
- The nightly invokes skills headlessly via `& claude --print $prompt --allowedTools "..."` and parses a trailing signal line (`[ae5-ok]` / `[ae5-skip]`).

---

# PHASE 2A — Safe legacy nightly improvement (prerequisite)

> 2A makes legacy republish non-destructive and wires 3-legacy/night into the nightly. It is the prerequisite for 2B (you cannot safely auto-improve legacy posts until republish stops blanking their meta / junking their TOC).

## Task 1: `adopt_legacy` captures the post's SEO description (blocker #1)

The 2026-06-10 gate proved that an adopted post has no `description` in frontmatter, so `republish_slug` (`desc = fm.get("description","")`) pushes an empty `_yoast_wpseo_metadesc` and **blanks the live meta description**. Fix: fetch and store the post's Yoast description at adoption.

**Files:**
- Modify: `scripts/lib/wp_client.py` (add `yoast_head_json` to `list_published_posts` `_fields`)
- Modify: `scripts/adopt_legacy.py` (`build_artifact` + `make_status_entry` read description)
- Test: `tests/test_adopt_legacy.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_adopt_legacy.py`:

```python
POST_WITH_YOAST = {
    "id": 17084,
    "slug": "power-bi-conditional-formatting-a-complete-guide",
    "link": "https://www.trainingint.com/power-bi-conditional-formatting-a-complete-guide.html",
    "title": {"rendered": "Power BI Conditional Formatting: A Complete Guide"},
    "content": {"rendered": "<p>body</p>"},
    "modified": "2024-01-01",
    "yoast_head_json": {
        "title": "Power BI Conditional Formatting: A Complete Guide Tutorial",
        "description": "Power BI conditional formatting guide for data bars & icons.",
    },
}


def test_build_artifact_captures_description_from_yoast():
    art = al.build_artifact("trainingint", POST_WITH_YOAST)
    fm_raw, _ = art.split("\n---\n", 1)
    fm = yaml.safe_load(fm_raw.lstrip("-\n"))
    assert fm["description"] == "Power BI conditional formatting guide for data bars & icons."


def test_build_artifact_no_description_key_when_yoast_absent():
    art = al.build_artifact("trainingint", POST)  # POST has no yoast_head_json
    fm_raw, _ = art.split("\n---\n", 1)
    fm = yaml.safe_load(fm_raw.lstrip("-\n"))
    assert "description" not in fm
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_adopt_legacy.py -k description -v`
Expected: FAIL — `KeyError: 'description'` / assertion error (no description captured).

- [ ] **Step 3: Implement**

In `scripts/lib/wp_client.py`, change the `_fields` line in `list_published_posts` to include `yoast_head_json`:

```python
        fields = "id,slug,link,title,content,modified,meta,acf,yoast_head_json"
```

In `scripts/adopt_legacy.py`, in `build_artifact`, after the `fm` dict is built and before the `cid` block, add:

```python
    desc = (post.get("yoast_head_json") or {}).get("description")
    if desc:
        fm["description"] = desc
```

In `make_status_entry`, after the `entry` dict and before the `cid` block, add the same:

```python
    desc = (post.get("yoast_head_json") or {}).get("description")
    if desc:
        entry["description"] = desc
```

**Build-time live check (do BEFORE trusting `_fields`):** run
`python -c "import os,yaml; from dotenv import load_dotenv; load_dotenv('credentials/.env'); s=yaml.safe_load(open('config/sites.yaml',encoding='utf-8'))['sites']['trainingint']; from scripts.lib.wp_client import WPClient; wp=WPClient(s['wp_api_base'], os.environ[s['app_password_env']+'_USER'], os.environ[s['app_password_env']]); print('yoast_head_json' in (wp.list_published_posts(per_page=1)[0]))"`
Expected: `True`. If `False`, WP isn't returning `yoast_head_json` in list queries — fall back to a per-post `wp.get_post(id)` in `_fetch_posts` to enrich each post with `yoast_head_json` before adoption, and note the change in the implementer report.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_adopt_legacy.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/wp_client.py scripts/adopt_legacy.py tests/test_adopt_legacy.py -- scripts/lib/wp_client.py scripts/adopt_legacy.py tests/test_adopt_legacy.py
git commit -m "feat(adopt): capture Yoast description so republish preserves meta" -- scripts/lib/wp_client.py scripts/adopt_legacy.py tests/test_adopt_legacy.py
```

---

## Task 2: `adopt_legacy` normalizes legacy heading misuse (blocker #2)

The gate proved legacy posts use `<h2>` for FAQ questions (`<h2>Q: …`) and author bios (`<h2>AUTHOR…`); `inject_toc` then lists all of them, producing a junk TOC (17 entries, 10 junk on post 17084). Fix: demote those non-section `<h2>`→`<h3>` in the body at adoption time.

**Files:**
- Modify: `scripts/adopt_legacy.py` (add `_normalize_legacy_headings`, call it in `build_artifact`)
- Test: `tests/test_adopt_legacy.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_normalize_demotes_faq_and_author_h2():
    body = ("<h2>Real Section</h2><p>x</p>"
            "<h2>Frequently Asked Questions</h2>"
            "<h2>Q: Is it free?</h2><p>A: yes</p>"
            "<h2>AUTHOR of this article: Vinai</h2>")
    out = al._normalize_legacy_headings(body)
    assert "<h2>Real Section</h2>" in out
    assert "<h2>Frequently Asked Questions</h2>" in out   # real section heading kept
    assert "<h3>Q: Is it free?</h3>" in out               # FAQ question demoted
    assert "<h3>AUTHOR of this article: Vinai</h3>" in out # author bio demoted
    assert "<h2>Q:" not in out and "<h2>AUTHOR" not in out


def test_build_artifact_body_has_no_misused_h2(monkeypatch):
    p = dict(POST_WITH_YOAST)
    p["content"] = {"rendered": "<h2>Q: x?</h2><p>a</p><h2>AUTHOR: v</h2>"}
    art = al.build_artifact("trainingint", p)
    _, body = art.split("\n---\n", 1)
    assert "<h2>Q:" not in body and "<h2>AUTHOR" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_adopt_legacy.py -k "normalize or misused" -v`
Expected: FAIL — `AttributeError: module 'scripts.adopt_legacy' has no attribute '_normalize_legacy_headings'`.

- [ ] **Step 3: Implement**

In `scripts/adopt_legacy.py`, add `import re` to the top imports (if absent), and add:

```python
# Legacy posts misuse <h2> for FAQ questions and author bios; inject_toc would
# then list them in the on-page TOC. Demote those non-section h2s to h3 at adoption.
_MISUSED_H2 = re.compile(r'<h2>((?:Q:|A:|AUTHOR).*?)</h2>', re.I | re.S)


def _normalize_legacy_headings(body):
    """Demote FAQ-question / author-bio <h2> to <h3>; keep real section headings."""
    return _MISUSED_H2.sub(r'<h3>\1</h3>', body)
```

In `build_artifact`, change the body line from:

```python
    body = post["content"]["rendered"]
```

to:

```python
    body = _normalize_legacy_headings(post["content"]["rendered"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_adopt_legacy.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Adversarial dry-run against the real fixture**

The post-17084 artifact already on disk was adopted pre-fix. Re-derive its body through the new normalizer and confirm a clean TOC, reusing the Phase-1 dry-run:

Run: `python -c "import re,yaml; from scripts import adopt_legacy as al, wp_publish as P; from scripts.republish import parse_seo_html; raw=open('content/trainingint/power-bi-conditional-formatting-a-complete-guide/_draft/04-seo.html',encoding='utf-8').read(); fm,body=parse_seo_html(raw); body=al._normalize_legacy_headings(body); h=P.inject_toc(body); import re as r; print('TOC entries:', len(r.findall(r'<li><a href=\"#', h))); print('junk:', len([m for m in r.findall(r'<li><a href=\"#[^\"]+\">([^<]*)</a>', h) if m.startswith('Q:') or m.startswith('AUTHOR')]))"`
Expected: `TOC entries: 7` and `junk: 0`.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(adopt): normalize legacy FAQ/author h2 misuse so TOC stays clean" -- scripts/adopt_legacy.py tests/test_adopt_legacy.py
```

---

## Task 3: Nightly "legacy trickle" phase — adopt 3 + improve those 3

`adopt_legacy.run(site, limit=3)` already adopts the first 3 untracked published posts and returns the count; it writes `source: legacy` status entries. The nightly must (a) call it, (b) improve exactly those 3 slugs, (c) keep the existing scheduled/published top-K improvement intact.

**Files:**
- Modify: `scripts/adopt_legacy.py` (`run` returns the adopted slugs, not just a count)
- Modify: `scripts/nightly_improve.ps1` (add a legacy phase)
- Test: `tests/test_adopt_legacy.py` (append)

- [ ] **Step 1: Write the failing test** (adopt returns the slugs it adopted)

```python
def test_run_returns_adopted_slugs(tmp_path, monkeypatch):
    _seed_project(tmp_path)
    monkeypatch.setattr(al, "ROOT", tmp_path)
    monkeypatch.setattr(al, "_fetch_posts", lambda site: [POST])
    adopted = al.run("trainingint", limit=3)
    assert adopted == ["how-to-group-on-canva-tutorial"]   # list of slugs, not a count
```

(Existing tests assert `al.run(...) == 1` / `== 0`. Update them to `len(al.run(...)) == 1` / `== []` in the SAME commit — a deliberate contract change updates its coupled tests.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adopt_legacy.py::test_run_returns_adopted_slugs -v`
Expected: FAIL — `assert 1 == ['how-to-group-on-canva-tutorial']`.

- [ ] **Step 3: Implement — `run` collects + returns slugs**

In `scripts/adopt_legacy.py` `run`, change the loop to collect slugs and return the list:

```python
def run(site, limit=None):
    """Adopt untracked published posts. Returns the list of slugs adopted."""
    _cfg, status_map, path = _load(site)
    today = date.today().isoformat()
    posts = _fetch_posts(site)

    adopted = []
    for post in posts:
        if limit is not None and len(adopted) >= limit:
            break
        if adopt_one(ROOT, site, post, status_map, today):
            adopted.append(post["slug"])
            print(f"  ADOPT {post['slug']} (post {post['id']})")

    if adopted:
        path.write_text(yaml.dump(status_map, allow_unicode=True, sort_keys=True),
                        encoding="utf-8")
    print(f"\nAdopted {len(adopted)} legacy post(s) into status/{site}.yaml")
    return adopted
```

Add a `--print-slugs` flag to `__main__` so the nightly can capture the adopted slugs:

```python
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("Usage: python -m scripts.adopt_legacy <site> [--limit N] [--print-slugs]")
    _site = args[0]
    _limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    _slugs = run(_site, limit=_limit)
    if "--print-slugs" in args:
        for s in _slugs:
            print(f"SLUG\t{s}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_adopt_legacy.py -v`
Expected: PASS (all, incl. the updated existing `run` tests).

- [ ] **Step 5: Add the legacy phase to `nightly_improve.ps1`**

In `scripts/nightly_improve.ps1`, after the Phase-1 triage block (around line 110, before "Phase 2: LLM improvement") add a new phase that adopts + records legacy slugs. Insert:

```powershell
# ─── Phase 1.5: legacy trickle — adopt N fresh legacy posts to improve tonight ──
$LEGACY_N = if ($env:AE_LEGACY_N) { [int]$env:AE_LEGACY_N } else { 3 }
$legacySlugs = @()
if ($LEGACY_N -gt 0) {
    foreach ($site in $sites) {
        Log "Adopting up to $LEGACY_N legacy post(s) for $site..."
        try {
            $out = & $PYTHON -m scripts.adopt_legacy $site --limit $LEGACY_N --print-slugs 2>&1
            $out | ForEach-Object {
                if ($_ -match '^SLUG\t(.+)$') { $legacySlugs += ,@($site, $Matches[1]) }
                else { Log "  $_" }
            }
            Log "$site adopted $(@($legacySlugs | Where-Object { $_[0] -eq $site }).Count) legacy post(s)"
        } catch {
            Log "ERROR adopting legacy for ${site}: $_"
        }
    }
}
```

Then, inside the Phase-2 `foreach ($site in $sites)` loop, AFTER the existing `$candidates = $triage.ranked | Select-Object -First $TOP_K` block builds the candidate list, prepend the tonight-adopted legacy slugs (as findings-bearing candidates) so they are improved this run. After the `$candidates` assignment add:

```powershell
        # Improve tonight's freshly-adopted legacy posts (in addition to top-K).
        $legacyForSite = @($legacySlugs | Where-Object { $_[0] -eq $site } | ForEach-Object { $_[1] })
        foreach ($ls in $legacyForSite) {
            if (-not ($candidates | Where-Object { $_.slug -eq $ls })) {
                $candidates = @($candidates) + ([pscustomobject]@{ slug = $ls; status = "published"; findings = @("[freshness] never improved") })
            }
        }
        Log "${site}: $($candidates.Count) candidate(s) (top-$TOP_K + $($legacyForSite.Count) legacy)"
```

(The existing `foreach ($article in $candidates)` loop then runs ae-5 on each, including the legacy ones; idempotency via the `_improve/` check is unchanged.)

- [ ] **Step 6: Smoke the legacy phase (no LLM, no live writes)**

Run: `$env:AE_SKIP_LLM="1"; $env:AE_LEGACY_N="2"; powershell -File scripts/nightly_improve.ps1`
Expected: log shows "Adopting up to 2 legacy post(s)…", `ADOPT <slug>` lines, and "adopted N legacy post(s)"; `status/trainingint.yaml` gains ≤2 `source: legacy` entries with a `description`. Phase 2 is skipped (AE_SKIP_LLM). Inspect one new artifact: body has no `<h2>Q:`/`<h2>AUTHOR`, frontmatter has `description`.

- [ ] **Step 7: Commit** (status/content are gitignored; commit only code)

```bash
git commit -m "feat(nightly): legacy trickle — adopt + improve 3 legacy posts/night" -- scripts/adopt_legacy.py scripts/nightly_improve.ps1 tests/test_adopt_legacy.py
```

---

# PHASE 2B — Independent SEO audit + prepared-fix loop

> Runs after each improvement is staged. Deterministic gate on every article; LLM depth only on flagged ones; surfaces issues + a prepared fix; applied on approval.

## Task 4: `audit_improvement.py` — deterministic gate over a staged `_improve`

**Files:**
- Create: `scripts/audit_improvement.py`
- Test: `tests/test_audit_improvement.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for post-improvement audit (scripts/audit_improvement.py)."""
from scripts import audit_improvement as ai


def test_big_issues_flags_error_severity_only():
    checks = [
        {"check": "body_h1_absent", "ok": False, "detail": "1 body h1", "severity": "error"},
        {"check": "content_img_alt", "ok": True, "detail": "0", "severity": "error"},
        {"check": "hreflang_en_sg", "ok": False, "detail": "absent", "severity": "info"},
    ]
    big = ai.big_issues(checks)
    assert [c["check"] for c in big] == ["body_h1_absent"]   # info-severity excluded


def test_audit_body_returns_record(tmp_path):
    body = "---\ntitle: t\n---\n<h1>dup</h1><img src='x.jpg'><p>hi</p>"
    rec = ai.audit_body(body)
    assert rec["needs_escalation"] is True          # body_h1 + img_alt both fail
    assert any(c["check"] == "body_h1_absent" for c in rec["big_issues"])
    assert rec["fix_plan"]                            # non-empty prepared-fix text


def test_clean_body_no_escalation():
    body = "---\ntitle: t\n---\n<h2>S</h2><p>clean</p>"
    rec = ai.audit_body(body)
    assert rec["needs_escalation"] is False
    assert rec["big_issues"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_audit_improvement.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.audit_improvement'`.

- [ ] **Step 3: Implement**

Create `scripts/audit_improvement.py`:

```python
"""Independent post-improvement SEO audit of a staged _improve/04-seo.html.

Deterministic gate: re-uses audit_live.audit_artifact_html (the engine's own
checklist) on the proposed 'after' body. Error-severity failures are the "big
issues"; their presence flags the article for escalation to claude-seo:seo-page
(LLM depth, run by the nightly via `claude -p`). Produces a per-article record
the dashboard/email render and that a prepared-fix step can act on.
"""
import json, sys, pathlib, yaml
from scripts.audit_live import audit_artifact_html
from scripts.lib.review import body_html

ROOT = pathlib.Path(__file__).resolve().parents[1]

# A prepared, human-readable fix for each deterministic check the gate can fail.
_FIX = {
    "body_h1_absent": "Demote the body <h1> to <h2> (WP renders the title as the page H1).",
    "jsonld_valid": "Fix the malformed JSON-LD block (matching braces/quotes) before publish.",
    "content_img_alt": "Add descriptive alt text to each content <img> missing it.",
}


def big_issues(checks):
    """Error-severity failures only (info-severity are advisory, not blocking)."""
    return [c for c in checks if not c["ok"] and c["severity"] == "error"]


def audit_body(text):
    """Audit one artifact string (frontmatter + body). Returns a record dict."""
    checks = audit_artifact_html(body_html(text))
    big = big_issues(checks)
    return {
        "big_issues": big,
        "needs_escalation": bool(big),
        "fix_plan": [_FIX.get(c["check"], f"Review and fix: {c['check']} ({c['detail']})")
                     for c in big],
    }


def audit_slug(root, site, slug):
    """Audit a slug's staged _improve; write _improve/audit.json. Returns the record."""
    art = pathlib.Path(root) / "content" / site / slug / "_improve" / "04-seo.html"
    rec = audit_body(art.read_text(encoding="utf-8"))
    rec["site"], rec["slug"] = site, slug
    (art.parent / "audit.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit("Usage: python -m scripts.audit_improvement <site> <slug> [slug...]")
    site = args[0]
    for slug in args[1:]:
        r = audit_slug(ROOT, site, slug)
        flag = "ESCALATE" if r["needs_escalation"] else "clean"
        print(f"[{flag}] {slug}: {len(r['big_issues'])} big issue(s)")
        for c in r["big_issues"]:
            print(f"    x {c['check']}: {c['detail']}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_audit_improvement.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(audit): independent post-improvement gate + prepared fix record" -- scripts/audit_improvement.py tests/test_audit_improvement.py
```

---

## Task 5: Escalate flagged articles to `claude-seo:seo-page`; merge into the record

**Files:**
- Modify: `scripts/nightly_improve.ps1` (call audit per staged slug; escalate flagged)
- Test: manual (the nightly orchestration has no unit test, by existing design)

- [ ] **Step 1: Add the audit+escalation block to `nightly_improve.ps1`**

Inside the Phase-2 `foreach ($article in $candidates)` loop, immediately AFTER the block that records a successful `[ae5-ok]` staging (after `Log "  OK: $okLine"`), add:

```powershell
                # Independent SEO audit of the staged 'after' (deterministic gate)
                try {
                    $auditJson = & $PYTHON -m scripts.audit_improvement $site $slug 2>&1
                    $auditJson | ForEach-Object { Log "    audit: $_" }
                    $auditRec = Get-Content "$ROOT\content\$site\$slug\_improve\audit.json" -Raw | ConvertFrom-Json
                    if ($auditRec.needs_escalation) {
                        Log "  ESCALATE $slug -> claude-seo:seo-page"
                        $url = (& $PYTHON -m scripts.slug_meta $site $slug | ConvertFrom-Json).$slug.url
                        $seoPrompt = "Invoke the claude-seo:seo-page skill for this URL: $url . Report only the top 3 highest-severity SEO issues, each one line, prefixed [seo]."
                        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
                        $seoOut = & $CLAUDE --print $seoPrompt --allowedTools "Bash,Read,WebFetch" 2>$null
                        $ErrorActionPreference = $savedEAP
                        $seoLines = @($seoOut | Where-Object { $_ -match '^\s*\[seo\]' } | ForEach-Object { $_.Trim() })
                        # merge the LLM findings into audit.json
                        $auditRec | Add-Member -NotePropertyName seo_page_findings -NotePropertyValue $seoLines -Force
                        ($auditRec | ConvertTo-Json -Depth 6) | Set-Content "$ROOT\content\$site\$slug\_improve\audit.json" -Encoding utf8
                        Log "  seo-page: $($seoLines.Count) finding(s)"
                    }
                } catch {
                    Log "  WARN audit failed for ${slug}: $_"
                }
```

(`claude-seo:seo-page` is a plugin skill — verify it's installed at build time: `ls ~/.claude/plugins/cache/*/claude-seo` should exist. It does as of 2026-06-10.)

- [ ] **Step 2: Manual smoke (one staged slug, real audit; LLM optional)**

Pre-req: one slug has a staged `_improve/04-seo.html` with a deliberate `<h1>` in the body. Run:
`python -m scripts.audit_improvement trainingint <slug>`
Expected: `[ESCALATE] <slug>: 1 big issue(s)` with `x body_h1_absent`; `content/trainingint/<slug>/_improve/audit.json` exists with `needs_escalation: true` and a `fix_plan`.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(nightly): audit each staged improvement, escalate flagged to claude-seo" -- scripts/nightly_improve.ps1
```

---

## Task 6: Surface audit + prepared fix in the AE review dashboard (:5001)

**Files:**
- Modify: `scripts/lib/review.py` (add `load_audit(root, site, slug)`)
- Modify: `scripts/review_server.py` (read audit.json per pending card; render issues + fix)
- Test: `tests/test_review.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_load_audit_reads_record(tmp_path):
    d = tmp_path / "content" / "trainingint" / "s" / "_improve"
    d.mkdir(parents=True)
    (d / "audit.json").write_text(
        '{"big_issues":[{"check":"content_img_alt","detail":"2 imgs","severity":"error","ok":false}],'
        '"fix_plan":["Add alt text"],"needs_escalation":true}', encoding="utf-8")
    rec = review.load_audit(tmp_path, "trainingint", "s")
    assert rec["needs_escalation"] is True
    assert rec["fix_plan"] == ["Add alt text"]


def test_load_audit_missing_is_none(tmp_path):
    assert review.load_audit(tmp_path, "trainingint", "nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_review.py -k load_audit -v`
Expected: FAIL — `AttributeError: module 'scripts.lib.review' has no attribute 'load_audit'`.

- [ ] **Step 3: Implement the loader**

In `scripts/lib/review.py` add (needs `import json` at top):

```python
def load_audit(root, site, slug):
    """Read content/<site>/<slug>/_improve/audit.json, or None if absent."""
    p = pathlib.Path(root) / "content" / site / slug / "_improve" / "audit.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_review.py -v`
Expected: PASS (all + 2 new).

- [ ] **Step 5: Render audit + fix in the dashboard card**

In `scripts/review_server.py`, in `_pending_with_diffs`, after the `r["blocks"] = ...` line add:

```python
        r["audit"] = review.load_audit(ROOT, r["site"], r["slug"])
```

In the `PAGE` template, immediately after the `.diff` card block (after its closing `</div>`), insert an audit panel:

```html
    {% if p.audit and p.audit.big_issues %}
    <div class="audit" style="background:#fff7f0;border:1px solid #f0d0b0;border-radius:8px;padding:10px 14px;margin:10px 0">
      <div class="tag">independent SEO audit — {{ p.audit.big_issues|length }} issue(s)</div>
      <ul style="margin:6px 0">
        {% for c in p.audit.big_issues %}<li><strong>{{ c.check }}</strong>: {{ c.detail }}</li>{% endfor %}
      </ul>
      <div class="tag">prepared fix (applied on approve)</div>
      <ul style="margin:6px 0">{% for f in p.audit.fix_plan %}<li>{{ f }}</li>{% endfor %}</ul>
      {% if p.audit.seo_page_findings %}<div class="tag">claude-seo:seo-page</div>
      <ul style="margin:6px 0">{% for s in p.audit.seo_page_findings %}<li>{{ s }}</li>{% endfor %}</ul>{% endif %}
    </div>
    {% endif %}
```

- [ ] **Step 6: Manual verification**

Pre-req: a staged slug with an `_improve/audit.json` carrying `big_issues`. Run `python -m scripts.review_server`, open `http://127.0.0.1:5001`. Expected: that card shows the orange audit panel listing issues + prepared fix (+ seo-page findings if present), above the existing diff/panes.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(review): surface independent audit + prepared fix per staged card" -- scripts/lib/review.py scripts/review_server.py tests/test_review.py
```

---

## Task 7: Apply the prepared fix on approval, then republish

`apply_improvement.apply_slug` already copies `_improve→_draft` and republishes published slugs. The prepared fix (currently for `body_h1_absent`) must be applied to the `_improve` body BEFORE the copy, so the republished page is corrected.

**Files:**
- Modify: `scripts/apply_improvement.py` (`apply_slug` applies deterministic fixes pre-copy)
- Test: `tests/test_apply_improvement.py` (create)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the pre-publish deterministic fix in apply_improvement."""
from scripts import apply_improvement as api


def test_apply_deterministic_fixes_demotes_body_h1():
    body = "<h1>Dup Title</h1><p>x</p>"
    out = api.apply_deterministic_fixes(body, ["body_h1_absent"])
    assert "<h1>" not in out and "<h2>Dup Title</h2>" in out


def test_apply_deterministic_fixes_noop_when_no_issue():
    body = "<h2>fine</h2>"
    assert api.apply_deterministic_fixes(body, []) == body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_apply_improvement.py -v`
Expected: FAIL — `AttributeError: module 'scripts.apply_improvement' has no attribute 'apply_deterministic_fixes'`.

- [ ] **Step 3: Implement**

In `scripts/apply_improvement.py` add (with `import re` at top):

```python
def apply_deterministic_fixes(body, issue_checks):
    """Apply the safe, deterministic prepared fixes named by issue_checks to a body."""
    if "body_h1_absent" in issue_checks:
        body = re.sub(r'<(/?)h1(\b[^>]*)>', r'<\1h2\2>', body, flags=re.I)
    return body
```

In `apply_slug`, BEFORE `shutil.copy2(improve_src, draft_dst)`, read any audit record and apply fixes to the `_improve` file in place:

```python
    audit_p = improve_src.parent / "audit.json"
    if audit_p.exists() and not dry_run:
        import json
        rec = json.loads(audit_p.read_text(encoding="utf-8"))
        checks = [c["check"] for c in rec.get("big_issues", [])]
        if checks:
            txt = improve_src.read_text(encoding="utf-8")
            fm, _, body = txt.partition("\n---\n")
            fixed = apply_deterministic_fixes(body, checks)
            if fixed != body:
                improve_src.write_text(fm + "\n---\n" + fixed, encoding="utf-8")
                print(f"  FIX  {slug}: applied {checks}")
```

(Non-deterministic / seo-page findings are advisory — surfaced for Vinai, not auto-applied. Keep that boundary.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_apply_improvement.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(apply): apply deterministic prepared fix before republish" -- scripts/apply_improvement.py tests/test_apply_improvement.py
```

---

## Task 8: PKM dashboard card — distinguish legacy + flag audit issues

The PKM dashboard already has `/api/ae-review/count` (counts `_improve/04-seo.html`) and `/tools/ae-review`. Enhance the count endpoint to also report how many staged items carry audit issues, so the card can say "3 legacy posts to review (2 with SEO issues)".

**Files:**
- Modify: `D:/VP/PKM/dashboard/server.py` (`/api/ae-review/count` also counts audit.json with big_issues)
- Modify: `D:/VP/PKM/dashboard/index.html` (card copy — verify current AE card markup first)

- [ ] **Step 1: Read the current card + endpoint**

Read `D:/VP/PKM/dashboard/server.py` lines 46–95 (the `_ae_port_open`, `api_ae_review_count`, `tools_ae_review` block) and grep `index.html` for `ae-review` to find the card markup. Do not guess the markup — match what exists.

- [ ] **Step 2: Extend the count endpoint**

In `api_ae_review_count`, after computing `n`, also count audited-with-issues:

```python
    import json as _json
    with_issues = 0
    for ap in AE_ROOT.glob("content/*/*/_improve/audit.json"):
        try:
            if _json.loads(ap.read_text(encoding="utf-8")).get("big_issues"):
                with_issues += 1
        except Exception:
            pass
    return jsonify({"count": n, "with_issues": with_issues})
```

- [ ] **Step 3: Update the card copy**

In `index.html`, update the AE card's JS that consumes `/api/ae-review/count` to show `with_issues` when > 0 (e.g., `${count} to review` + `(${with_issues} with SEO issues)`). Match the existing fetch/render idiom in that file.

- [ ] **Step 4: Manual verification**

Run the PKM dashboard (`python D:/VP/PKM/dashboard/server.py`, open `http://localhost:5000`) with ≥1 staged improvement that has an `audit.json` with `big_issues`. Expected: the AE card shows the count and the "N with SEO issues" sub-line, and clicking it opens the AE review dashboard.

- [ ] **Step 5: Commit (PKM dashboard repo)**

```bash
cd /d/VP/PKM/dashboard && git add server.py index.html && git commit -m "feat(ae-card): show legacy review count + audit-issue flag"
```

---

## Self-Review (completed by plan author)

**Spec coverage (locked decisions → tasks):**
- One job, extend AE-NightlyImprove → Tasks 3, 5 (no new cron). ✓
- Trickle adopt+improve 3 legacy/night → Task 3. ✓
- Blocker #1 (meta capture) → Task 1. ✓  Blocker #2 (heading normalize) → Task 2. ✓
- Audit = deterministic gate every article → Task 4; escalate flagged to claude-seo:seo-page → Task 5. ✓
- Fix model = surface + prepared fix, apply on approval → Tasks 4 (record+fix_plan), 6 (surface), 7 (apply-on-approve). ✓
- Review in AE dashboard (:5001) → Task 6; PKM dashboard card (:5000) → Task 8. ✓

**Type consistency:** `audit_body`/`audit_slug` write `audit.json` with keys `{big_issues, needs_escalation, fix_plan, site, slug}` (+ `seo_page_findings` after Task 5); consumed with those exact keys in `review.load_audit` (Task 6), `apply_slug` (Task 7), and the PKM endpoint (Task 8). `adopt_legacy.run` returns `list[str]` (Task 3) — existing count-based tests updated in the same commit. `apply_deterministic_fixes(body, issue_checks)` matches its call in `apply_slug`.

**Known residual risks / to verify at build time (live checks, not assumptions):**
- `yoast_head_json` in `list_published_posts` `_fields` (Task 1 Step 3 live check; fallback = per-post `get_post`).
- `claude-seo:seo-page` headless invocation shape + its output (Task 5 — verify the skill is installed and that `--print` returns parseable `[seo]` lines; if it needs a URL vs content, adjust the prompt).
- The post-title vs Yoast-title conflation (Phase-1 finding) is NOT fixed here — adopted posts still can't carry a Yoast title distinct from the post title. Out of scope for Phase 2; revisit if needed.
- Task 2's `_MISUSED_H2` is heuristic (Q:/A:/AUTHOR prefixes). Run the Task 2 Step 5 corpus check on several real adopted bodies before bulk reliance; widen the pattern if a real legacy post uses a different misuse shape.

**Deferred (correctly out of Phase 2):** post-republish LIVE audit (audit_html on the live page after approval) as a confirmation pass; auto-applying non-deterministic seo-page findings; multi-site (only `trainingint`).
