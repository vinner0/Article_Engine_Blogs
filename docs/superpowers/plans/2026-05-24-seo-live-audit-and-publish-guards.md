# SEO Live-Audit + Publish Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the engine from shipping pages that pass the artifact checklist but break once WordPress renders them — specifically the duplicate-`<h1>` leak (24 of 33 artifacts, incl. 4 of 6 scheduled posts) and malformed live FAQ JSON-LD (Outlook) — by adding two fail-closed publish-time guards and a re-fetch-the-live-URL audit tool.

**Architecture:** Both new guards live inside `publish_article()` in `scripts/wp_publish.py` — the single choke-point that *both* fresh publishes and `scripts/republish.py` already flow through, so fixing it once fixes the whole corpus and all future posts. A new standalone `scripts/audit_live.py` re-fetches published URLs (and, for the not-yet-live scheduled queue, reads local artifacts) and re-runs the *rendered-HTML-checkable* subset of the 80-item checklist — the root-cause fix for "we only ever validated the artifact, never the live page" (task-observer Observation 95). Checklist item #51 (hreflang) is reclassified to the manual/WP doc, since Yoast-free cannot emit it and the engine never has.

**Tech Stack:** Python 3.13, `pytest`, `responses` (HTTP mocking, already used in `tests/test_wp_publish.py`), `requests`, stdlib `re`/`json`. No new dependencies.

---

## Background / evidence (read once before starting)

Audit of the 4 live pages + scan of all 33 `_draft/04-seo.html` artifacts on 2026-05-24:

- **Duplicate H1 (engine bug, widespread).** WordPress/Elementor renders the post *title* as the page `<h1>`. 24 of 33 artifacts ALSO contain an `<h1>` in the body (e.g. `content/trainingint/how-to-use-copilot-in-outlook/_draft/04-seo.html:54`), so the live page renders two `<h1>`. The 3 clean published pages (filter/teams/vlookup) have zero body `<h1>` — proof the body H1 is the defect, not the norm. Affected scheduled posts that go live 2026-05-26..06-01: `how-to-create-pivot-tables-in-excel`, `how-to-use-copilot-in-powerpoint`, `how-to-use-copilot-in-word`, `how-to-use-sumif-and-sumifs-in-excel`.
- **Malformed live FAQ JSON-LD (publish/render-layer bug).** `how-to-use-copilot-in-outlook` live page: the `<script type="application/ld+json">` FAQPage block fails `json.loads` with `Extra data` (JSON object followed by `<\/script></p>…` inside one script tag) → no FAQ rich result. The other 3 live pages parse fine. **`build_jsonld()` itself is correct and well-tested** (`tests/test_jsonld.py::test_script_breakout_escaped`) — the corruption happens after the builder, so the only reliable catch is (a) a publish-time parse of the *outgoing* embedded JSON-LD and (b) a parse of the *live rendered* page.
- **hreflang `en-SG` absent on all 4 live pages.** Checklist #51 claims it; the engine has never emitted it (`grep -rl hreflang scripts/ config/` → nothing). It is a `<head>` link tag Yoast-free won't produce. Decision (Vinai, 2026-05-24): reclassify as manual/WP, do NOT fake-pass it.
- **Non-issues confirmed:** meta-description em-dash is real UTF-8 (`e2 80 94`), not mojibake; the only alt-less image is the 1×1 `display:none` Facebook pixel (correct).

Saved evidence for building production-shaped test fixtures lives under `.tmp/audit/` (`outlook.html`, `filter.html`, `teams.html`, `vlookup.html`, `scan_artifacts.py`). **Do not import from `.tmp/` in tests** — `.tmp` is throwaway. Copy the minimal real-shaped fragments into the test files as literals.

---

## File structure

- **Modify** `scripts/wp_publish.py` — add `strip_body_h1(html)` and `assert_jsonld_valid(html, slug)`; wire both into `publish_article()`.
- **Create** `scripts/audit_live.py` — `audit_html(html, expected_url=None) -> list[Check]`, `fetch(url)`, `audit_artifact(path)`, and a CLI over `status/<site>.yaml`.
- **Modify** `tests/test_wp_publish.py` — add tests for the two new guards (incl. adversarial + production-shaped).
- **Create** `tests/test_audit_live.py` — tests for `audit_html` against a production-shaped page fragment.
- **Modify** `seo/checklist.md` — reclassify #51 hreflang from a PASS/FAIL engine item to a manual/WP pointer.
- **Modify** `docs/seo-ops-checklist.md` — add the hreflang manual item under "High impact".

### Key design decision to confirm in review (flag for codex + Vinai)

`strip_body_h1` **demotes** every body `<h1>`→`<h2>` rather than deleting it. Rationale: non-destructive (no content lost even when a body `<h1>` is not a title-echo), deterministic, idempotent, and it satisfies checklist #9 ("exactly one `<h1>`") because WP supplies the canonical title `<h1>`. The alternative — *delete* an `<h1>` whose text matches the title and demote the rest — yields a cleaner page when the body H1 is a pure title restatement, but it would **not fire for the real Outlook case** (its body H1 text "…A Practical Walkthrough" differs from the WP title "…(Full Walkthrough)"), so it is both more complex and less effective here. The plan implements **demote-all**. Ordering note (corrected per codex audit): `inject_toc()` only scans `<h2>`, so `strip_body_h1` is order-independent relative to it — running it after `inject_toc` is just the logical "all content transforms done, now the pre-write checkpoints" position, NOT a TOC-exclusion requirement. Accepted SEO tradeoff: a demoted H1 becomes an H2 that may read as a mild restatement near the top; this is a content-editing nicety, not a structural violation.

---

## Task 1: `strip_body_h1` — demote body `<h1>` to `<h2>`

**Files:**
- Modify: `scripts/wp_publish.py` (add function near `inject_toc`, ~line 68; wire into `publish_article` ~line 108)
- Test: `tests/test_wp_publish.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_wp_publish.py`)

```python
from scripts.wp_publish import strip_body_h1   # add to the existing import line at top

def test_strip_body_h1_demotes_to_h2():          # core contract
    # production-shaped: real Outlook artifact body H1 (04-seo.html:54)
    html = ('<p>intro</p>'
            '<h1>How to Use Copilot in Outlook in 2026: A Practical Walkthrough</h1>'
            '<h2>Setup</h2><p>body</p>')
    out = strip_body_h1(html)
    assert '<h1' not in out and '</h1>' not in out          # ADVERSARIAL: no-op stub fails here
    assert ('<h2>How to Use Copilot in Outlook in 2026: A Practical Walkthrough</h2>'
            in out)
    assert '<h2>Setup</h2>' in out                          # untouched real h2 survives

def test_strip_body_h1_idempotent():
    html = '<h1>Title</h1><h2>x</h2>'
    once = strip_body_h1(html)
    assert strip_body_h1(once) == once                      # ADVERSARIAL: a global re-run must not corrupt

def test_strip_body_h1_preserves_h1_attributes():
    html = '<h1 class="lead" id="top">Title</h1>'
    out = strip_body_h1(html)
    assert out == '<h2 class="lead" id="top">Title</h2>'

def test_strip_body_h1_noop_when_no_body_h1():
    html = '<h2>only h2 here</h2><p>x</p>'                   # the 3 clean published pages
    assert strip_body_h1(html) == html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wp_publish.py -k strip_body_h1 -v`
Expected: FAIL — `ImportError: cannot import name 'strip_body_h1'`

- [ ] **Step 3: Implement `strip_body_h1`** (add after `inject_toc`, before `upload_featured`, in `scripts/wp_publish.py`)

```python
def strip_body_h1(html):
    """WordPress renders the post title as the page <h1>; any <h1> in the body is
    therefore a duplicate (checklist #9). Demote every body <h1> to <h2> — non-
    destructive (no content lost), deterministic, idempotent. Preserves the tag's
    attributes (class/id) by rewriting only the tag name. Order-independent vs
    inject_toc (which only scans <h2>); placed after the content transforms as the
    last pre-write content normalization."""
    return re.sub(r'<(/?)h1(\b[^>]*)>', r'<\1h2\2>', html, flags=re.I)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wp_publish.py -k strip_body_h1 -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Wire into `publish_article`** (in `scripts/wp_publish.py`, immediately after the `if add_toc: html = inject_toc(html)` block, ~line 108)

```python
    if add_toc:
        html = inject_toc(html)
    html = strip_body_h1(html)   # WP supplies the page <h1> (title); demote any body <h1> (order vs inject_toc is irrelevant — it only scans <h2>)
```

- [ ] **Step 6: Add a publish-path integration test** (append to `tests/test_wp_publish.py`)

```python
@responses.activate
def test_publish_demotes_body_h1():   # B: wired through publish, no double-H1 ships
    # Mirrors test_first_publish_creates_scheduled exactly: module-level WP/AE
    # constants, the {AE}/find uid route, the {WP}/posts slug+create routes, and
    # reads the create POST body (bytes) from responses.calls[-1].
    responses.get(f"{AE}/find", status=404)             # uid not found
    responses.get(f"{WP}/posts", json=[], status=200)   # slug not found
    responses.post(f"{WP}/posts", json={"id": 100}, status=201)
    publish_article(wp(), "uid1", "how-to-x", "Real Title",
                    "<h1>Real Title</h1><h2>A</h2><p>x</p>", {}, "2026-06-01T09:00:00", 5, 1)
    body = responses.calls[-1].request.body             # bytes of the create POST
    assert b"<h1" not in body          # ADVERSARIAL: drop the strip_body_h1 wiring line -> fails
    assert b"<h2>Real Title</h2>" in body
```

> Verified against `tests/test_wp_publish.py:4-16`: `WP="https://www.trainingint.com/wp-json/wp/v2"`, `AE="…/ae/v1"`, `def wp(): return WPClient(WP,"u","p")`, uid route is `{AE}/find` (404 = not found), and the create body is read via `responses.calls[-1].request.body`. Do NOT introduce a new `WPClient(...)` or `x.test` URL — use the existing constants and `wp()`.

- [ ] **Step 7: Run the new integration test**

Run: `python -m pytest tests/test_wp_publish.py -k "demotes_body_h1" -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/wp_publish.py tests/test_wp_publish.py
git commit -m "fix: demote body <h1> to <h2> at publish (WP owns the page H1)"
```

---

## Task 2: `assert_jsonld_valid` — fail-closed gate on outgoing embedded JSON-LD

**Files:**
- Modify: `scripts/wp_publish.py` (add function near `_AE_TOKEN`, ~line 11; wire into `publish_article` after `strip_body_h1`)
- Test: `tests/test_wp_publish.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_wp_publish.py`)

```python
from scripts.wp_publish import assert_jsonld_valid   # add to the import line
import pytest

def test_assert_jsonld_valid_passes_clean_block():
    from scripts.lib.jsonld import build_jsonld
    j = build_jsonld("https://x.test/p", "T", "d", "Vinai", "Org",
                     faqs=[{"q": "Q1?", "a": "use </script> safely"}],
                     breadcrumb=[("Home", "https://x.test/")])
    html = f'<p>body</p><script type="application/ld+json">{j}</script>'
    assert_jsonld_valid(html, "slug")          # must NOT raise (the </ -> <\/ guard is json.loads-safe)

def test_assert_jsonld_valid_rejects_extra_data():   # production-shaped: the real Outlook live failure
    # one <script> tag holding a complete JSON object THEN trailing markup before </script>
    broken = ('<script type="application/ld+json">'
              '{"@context":"https://schema.org","@graph":[{"@type":"FAQPage",'
              '"mainEntity":[{"@type":"Question","name":"Q?","acceptedAnswer":'
              '{"@type":"Answer","text":"a"}}]}]}<\\/script></p><div>elementor junk'
              '</script>')
    with pytest.raises(ValueError, match="JSON-LD"):
        assert_jsonld_valid(broken, "how-to-use-copilot-in-outlook")
    # ADVERSARIAL: a no-op stub that never calls json.loads will NOT raise here, so
    # pytest.raises(ValueError) reports "DID NOT RAISE" — i.e. the test fails unless the
    # parse logic is real. (The `broken` block is the real Outlook live shape: a complete
    # JSON object followed by appended markup before the real </script> -> "Extra data".)

def test_assert_jsonld_valid_ignores_non_ldjson_scripts():
    html = '<script>var x=1;</script><p>no ld+json here</p>'
    assert_jsonld_valid(html, "slug")          # must NOT raise (no ld+json blocks)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wp_publish.py -k assert_jsonld_valid -v`
Expected: FAIL — `ImportError: cannot import name 'assert_jsonld_valid'`

- [ ] **Step 3: Implement `assert_jsonld_valid`** (add after the `_AE_TOKEN` definition, ~line 11, in `scripts/wp_publish.py`)

```python
import json   # add to the top-of-file import line

# Match each in-HTML JSON-LD block exactly as a browser/Google parser would: the
# non-greedy (.*?) stops at the first REAL </script>; an escaped <\/script> inside
# the JSON (ae-6's breakout guard) is correctly skipped. json.loads handles the
# valid \/ escape, so a clean block parses; a block with markup appended before the
# real </script> raises "Extra data" — which is the Outlook live failure we must catch.
_LDJSON = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.I | re.S)

def assert_jsonld_valid(html, slug):
    """Fail-closed: every embedded application/ld+json block in the OUTGOING html
    must parse. Mirrors the _AE_TOKEN gate — runs before the WP POST write so a
    refusal does not create/update the post. (Inline media is uploaded earlier in
    publish_article, so a refusal here can still leave orphaned media — same as the
    existing _AE_TOKEN gate; acceptable for this backfill.) Catches the publish/
    render-layer corruption the pre-publish checklist (which trusts build_jsonld)
    cannot see."""
    for i, block in enumerate(_LDJSON.findall(html)):
        try:
            json.loads(block)
        except ValueError as e:
            raise ValueError(
                f"invalid JSON-LD block #{i} in {slug!r}, refusing to publish: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wp_publish.py -k assert_jsonld_valid -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Wire into `publish_article`** (in `scripts/wp_publish.py`, right after the `strip_body_h1` line added in Task 1, and just before the `residual = _AE_TOKEN.findall(html)` gate)

```python
    html = strip_body_h1(html)
    assert_jsonld_valid(html, slug)   # fail-closed: no malformed FAQ/Article schema ships
    residual = _AE_TOKEN.findall(html)
```

- [ ] **Step 6: Run the full publish suite (no regressions)**

Run: `python -m pytest tests/test_wp_publish.py -v`
Expected: PASS (all prior tests + new ones)

- [ ] **Step 7: Commit**

```bash
git add scripts/wp_publish.py tests/test_wp_publish.py
git commit -m "fix: fail-closed gate rejects malformed embedded JSON-LD before publish"
```

---

## Task 3: `scripts/audit_live.py` — re-fetch the live page and re-run the rendered-checkable checks

**Files:**
- Create: `scripts/audit_live.py`
- Test: `tests/test_audit_live.py`

The core is a pure function `audit_html(html, expected_url=None)` so it is testable without network. `fetch()` and the CLI are thin wrappers.

- [ ] **Step 1: Write the failing tests** (create `tests/test_audit_live.py`)

```python
from scripts.audit_live import audit_html

# Production-shaped page fragment: a theme title <h1> + a leaked body <h1> (the live
# Outlook shape), one valid ld+json, one broken ld+json, a canonical, a meta desc,
# and a 1x1 display:none tracking pixel (the only legit alt-less image).
GOOD_LD = '{"@context":"https://schema.org","@graph":[{"@type":"Article"}]}'
BAD_LD = '{"@type":"FAQPage"}<\\/script></p><div>junk'  # JSON + appended markup

def _page(h1s=1, good_ld=True, bad_ld=False, canonical="https://x.test/p",
          meta="x"*150, pixel=True):
    parts = ['<head>']
    if canonical:
        parts.append(f'<link rel="canonical" href="{canonical}"/>')
    if meta is not None:
        parts.append(f'<meta name="description" content="{meta}"/>')
    parts.append('</head><body>')
    for i in range(h1s):
        parts.append(f'<h1>Title {i}</h1>')
    if good_ld:
        parts.append(f'<script type="application/ld+json">{GOOD_LD}</script>')
    if bad_ld:
        parts.append(f'<script type="application/ld+json">{BAD_LD}</script>')
    if pixel:
        parts.append('<img height="1" width="1" style="display:none" '
                     'src="https://www.facebook.com/tr?id=1"/>')
    parts.append('<img src="/hero.webp" alt="real hero"/></body>')
    return "".join(parts)

def _result(checks, name):
    return next(c for c in checks if c["check"] == name)

def test_single_h1_passes():
    assert _result(audit_html(_page(h1s=1)), "single_h1")["ok"] is True

def test_double_h1_fails():     # ADVERSARIAL: a stub that hardcodes ok=True fails here
    r = _result(audit_html(_page(h1s=2)), "single_h1")
    assert r["ok"] is False and "2" in r["detail"]

def test_broken_jsonld_fails():
    assert _result(audit_html(_page(bad_ld=True)), "jsonld_valid")["ok"] is False

def test_clean_jsonld_passes():
    assert _result(audit_html(_page(good_ld=True, bad_ld=False)), "jsonld_valid")["ok"] is True

def test_canonical_match():
    checks = audit_html(_page(canonical="https://x.test/p"), expected_url="https://x.test/p")
    assert _result(checks, "canonical")["ok"] is True
    bad = audit_html(_page(canonical="https://x.test/other"), expected_url="https://x.test/p")
    assert _result(bad, "canonical")["ok"] is False

def test_meta_length_band():
    assert _result(audit_html(_page(meta="x"*150)), "meta_desc_len")["ok"] is True
    assert _result(audit_html(_page(meta="x"*40)), "meta_desc_len")["ok"] is False

def test_tracking_pixel_not_counted_as_missing_alt():   # only the FB pixel lacks alt -> still PASS
    assert _result(audit_html(_page(pixel=True)), "content_img_alt")["ok"] is True

def test_hreflang_reported_not_failed():   # #51 reclassified manual: report absence, do NOT fail
    r = _result(audit_html(_page()), "hreflang_en_sg")
    assert r["severity"] == "info"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_audit_live.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.audit_live'`

- [ ] **Step 3: Implement `scripts/audit_live.py`**

```python
"""Post-publish live-page SEO audit. Re-fetches a published URL and re-runs the
subset of the 80-item checklist that can only be verified on the RENDERED page
(WordPress/Elementor/Yoast transform the artifact before it goes live, so an
artifact-only checklist passes pages that are actually broken — see task-observer
Observation 95). For not-yet-live scheduled posts, audit the local artifact body.

Usage:
  python -m scripts.audit_live trainingint                 # all published live URLs
  python -m scripts.audit_live trainingint --scheduled     # scheduled queue, via artifacts
  python -m scripts.audit_live trainingint <slug> [slug..] # specific slugs (live)
"""
import os, re, sys, json, pathlib, requests, yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
_LDJSON = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.I | re.S)

def _check(name, ok, detail="", severity="error"):
    return {"check": name, "ok": bool(ok), "detail": detail, "severity": severity}

def _tag_attr(html, tag_pattern, attr):
    """Find the first tag matching tag_pattern, then extract `attr` from inside it,
    independent of attribute order. Returns the value or None."""
    m = re.search(tag_pattern, html, re.I)
    if not m:
        return None
    a = re.search(attr + r'=["\'](.*?)["\']', m.group(0), re.I)
    return a.group(1) if a else None

def audit_html(html, expected_url=None):
    """Return a list of check dicts: {check, ok, detail, severity}. Pure — no IO."""
    checks = []

    h1s = re.findall(r'<h1\b', html, re.I)
    checks.append(_check("single_h1", len(h1s) == 1, f"found {len(h1s)} <h1>"))

    bad = []
    blocks = _LDJSON.findall(html)
    for i, b in enumerate(blocks):
        try:
            json.loads(b)
        except ValueError as e:
            bad.append(f"#{i}: {e}")
    checks.append(_check("jsonld_valid", not bad,
                         f"{len(blocks)} block(s); bad: {bad}" if bad else f"{len(blocks)} ok"))

    # Order-independent: find the whole tag first, then pull the attribute from it,
    # so `rel`-before-`href` (Yoast) and `href`-before-`rel` both work.
    can = _tag_attr(html, r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>', 'href')
    if expected_url is None:
        checks.append(_check("canonical", bool(can), can or "missing"))
    else:
        checks.append(_check("canonical", can == expected_url, f"{can!r} vs {expected_url!r}"))

    desc = _tag_attr(html, r'<meta\b[^>]*\bname=["\']description["\'][^>]*>', 'content') or ""
    checks.append(_check("meta_desc_len", 140 <= len(desc) <= 160, f"{len(desc)} chars"))

    # Content images missing alt — exclude tracking pixels by BOTH dimension/style
    # (1x1 / display:none) AND known-pixel URL (e.g. facebook.com/tr).
    missing = 0
    for img in re.findall(r'<img[^>]*>', html, re.I):
        if re.search(r'\balt=', img, re.I):
            continue
        if re.search(r'(width=["\']?1\b|height=["\']?1\b|display:\s*none|'
                     r'visibility:\s*hidden|opacity:\s*0|facebook\.com/tr|/pixel|utm\.gif)',
                     img, re.I):
            continue            # tracking pixel — not a content image
        missing += 1
    checks.append(_check("content_img_alt", missing == 0, f"{missing} content img(s) w/o alt"))

    has_hl = bool(re.search(r'hreflang=["\']en-?SG["\']', html, re.I))
    checks.append(_check("hreflang_en_sg", has_hl,
                         "present" if has_hl else "absent (manual/WP item #51)",
                         severity="info"))

    return checks

def fetch(url, timeout=30):
    r = requests.get(url, headers={"User-Agent": "ae-audit/1.0"}, timeout=timeout)
    r.raise_for_status()
    return r.text

def audit_artifact(path):
    """Audit a local _draft/04-seo.html body (for scheduled posts not yet live)."""
    return audit_html(pathlib.Path(path).read_text(encoding="utf-8"))

def _print(label, checks):
    fails = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    infos = [c for c in checks if not c["ok"] and c["severity"] == "info"]
    mark = "FAIL" if fails else "ok"
    print(f"[{mark}] {label}")
    for c in fails:
        print(f"    x {c['check']}: {c['detail']}")
    for c in infos:
        print(f"    i {c['check']}: {c['detail']}")
    return not fails

def run(site, slugs=None, scheduled=False):
    status_map = yaml.safe_load((ROOT / f"status/{site}.yaml").read_text()) or {}
    content_root = ROOT / "content" / site
    if scheduled:
        targets = [s for s, v in status_map.items() if v.get("status") == "scheduled"]
    elif slugs:
        targets = slugs
    else:
        targets = [s for s, v in status_map.items() if v.get("status") == "published"]
    all_ok = True
    for slug in targets:
        entry = status_map.get(slug, {})
        try:
            if scheduled:
                art = content_root / slug / "_draft" / "04-seo.html"
                checks = audit_artifact(art)
                label = f"{slug} (artifact)"
            else:
                url = entry.get("url")
                if not url:
                    raise ValueError(f"no 'url' in status_map for {slug!r}")
                checks = audit_html(fetch(url), expected_url=url)
                label = f"{slug} -> {url}"
        except Exception as e:
            print(f"[ERR ] {slug}: {type(e).__name__}: {e}")
            all_ok = False
            continue
        all_ok = _print(label, checks) and all_ok
    return all_ok

if __name__ == "__main__":
    args = sys.argv[1:]
    site = args[0] if args else "trainingint"
    scheduled = "--scheduled" in args
    slug_args = [a for a in args[1:] if not a.startswith("--")]
    ok = run(site, slug_args or None, scheduled=scheduled)
    sys.exit(0 if ok else 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_audit_live.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_live.py tests/test_audit_live.py
git commit -m "feat: scripts/audit_live.py re-fetches live pages and re-runs rendered-HTML SEO checks"
```

---

## Task 4: Reclassify checklist #51 (hreflang) as manual/WP

**Files:**
- Modify: `seo/checklist.md` (item #51 under "Technical / snippet bait")
- Modify: `docs/seo-ops-checklist.md` (add under "## High impact")

- [ ] **Step 1: Edit `seo/checklist.md`** — replace the line:

```
51. `hreflang="en-SG"` present
```

with:

```
51. `hreflang="en-SG"` present — **MANUAL/WP (not engine-checkable).** Yoast-free does not emit hreflang and the engine never injects `<head>` link tags; verified absent on all live pages 2026-05-24. Tracked in `docs/seo-ops-checklist.md`. `audit_live.py` reports its presence as INFO, never FAIL.
```

- [ ] **Step 2: Edit `docs/seo-ops-checklist.md`** — add under "## High impact":

```
- [ ] **hreflang `en-SG`.** Absent on all live pages (checklist #51 reclassified — the engine cannot
      emit `<head>` link tags and Yoast-free has no hreflang). If you want it, add via a hreflang
      plugin or Yoast Premium; for a single-locale SG site it is low-value. `audit_live.py` reports
      presence as INFO only.
```

- [ ] **Step 3: Verify the transform landed (positive + negative assertion — see writing-plans delta on transform+verify gates)**

Run (PowerShell, the session shell): `Select-String -Path seo/checklist.md -Pattern "MANUAL/WP \(not engine-checkable\)"; (Select-String -Path docs/seo-ops-checklist.md -Pattern "hreflang").Count`
(bash equivalent: `grep -n "MANUAL/WP (not engine-checkable)" seo/checklist.md && grep -c "hreflang" docs/seo-ops-checklist.md`)
Expected: the `seo/checklist.md` line prints; `docs/seo-ops-checklist.md` hreflang count ≥ 1.

- [ ] **Step 4: Commit**

```bash
git add seo/checklist.md docs/seo-ops-checklist.md
git commit -m "docs: reclassify hreflang #51 as manual/WP (engine cannot emit head tags)"
```

---

## Task 5: Backfill — re-audit the scheduled queue, then re-publish the broken posts

This is the operational payoff. The two guards now run inside `publish_article`, so `scripts/republish.py` (which calls `publish_article`) automatically demotes body H1 and validates JSON-LD on every re-push.

- [ ] **Step 1: Audit the scheduled queue against the artifacts (before re-push)**

Run: `python -m scripts.audit_live trainingint --scheduled`
Expected: `single_h1` FAILs for `how-to-create-pivot-tables-in-excel`, `how-to-use-copilot-in-powerpoint`, `how-to-use-copilot-in-word`, `how-to-use-sumif-and-sumifs-in-excel`; clean for `essential-excel-formulas-every-finance-professional-needs` and `how-to-use-copilot-in-excel`. (This is the predicted baseline — if it differs, STOP and reconcile before re-publishing.)

- [ ] **Step 2: Audit the 4 live published pages**

Run: `python -m scripts.audit_live trainingint`
Expected: `how-to-use-copilot-in-outlook` FAILs `single_h1` and `jsonld_valid`; the other 3 pass all error-severity checks.

- [ ] **Step 3: Re-publish Outlook (live, broken) — guards now fix it in flight**

Run: `python -m scripts.sync_status trainingint` then `python -m scripts.republish trainingint how-to-use-copilot-in-outlook`
Expected: `OK how-to-use-copilot-in-outlook -> post 17478`. (Confirm `sync_status` is the correct pre-step per `scripts/republish.py` docstring lines 5–6.)

- [ ] **Step 4: Re-audit Outlook live to confirm the fix**

Run: `python -m scripts.audit_live trainingint how-to-use-copilot-in-outlook`
Expected: all error-severity checks PASS (single_h1 ok, jsonld_valid ok).

- [ ] **Step 5: Re-push the 4 affected scheduled posts**

These are future-dated; `republish.py` fetches each live post via `wp.get_post(entry["wp_post_id"])` and re-passes its existing `status` (`"future"`) + `date`, so re-pushing keeps them scheduled. **Prerequisite (per `republish.py` docstring + codex M2):** the status YAML entry MUST carry `wp_post_id` — run `sync_status` first or `republish_slug` will `KeyError`. The default `republish` run only targets `status == "published"` entries, so the scheduled slugs MUST be passed explicitly (as below).

Run: `python -m scripts.sync_status trainingint` then `python -m scripts.republish trainingint how-to-create-pivot-tables-in-excel how-to-use-copilot-in-powerpoint how-to-use-copilot-in-word how-to-use-sumif-and-sumifs-in-excel`
Expected: `OK` for each. Note: `how-to-use-copilot-in-powerpoint` artifact has no FAQ schema — re-audit will still pass (FAQ presence is not an error-severity check in `audit_live`); FAQ *enrichment* for that post is out of scope here (see "Out of scope" below).

- [ ] **Step 6: Final re-audit of scheduled artifacts**

Run: `python -m scripts.audit_live trainingint --scheduled`
Expected: no `single_h1` FAILs remain.

> No commit — this task changes live/scheduled WordPress state, not the repo. Record the run output in the session log.

---

## Out of scope (record, do not implement here)

- **Missing FAQ schema on some posts** (`how-to-use-copilot-in-powerpoint` scheduled + several unpublished drafts). `audit_live` reports JSON-LD *validity*, not FAQ *presence*; adding FAQ blocks is an ae-6 content task, not a publish guard.
- **Cross-domain consolidation, `.html`→clean URLs, hero LCP/lazy-load** — already tracked in `docs/seo-ops-checklist.md`; WP-level, not engine.
- **hreflang implementation** — deliberately reclassified manual (Task 4), per Vinai 2026-05-24.
- **Unpublished drafts** (19 with body H1) — fixed automatically whenever they go through `publish_article`; no backfill needed since they are not live.

---

## Self-review (completed by plan author)

**Spec coverage:** A (live audit) → Task 3 + Task 5 Steps 1–2,4,6. B (body-H1) → Task 1 + Task 5. C (FAQ JSON-LD) → Task 2 (publish gate) + Task 3 (live check) + Task 5 Step 2,4. D (hreflang) → Task 4. Scheduled-queue risk (Vinai's question) → Task 3 `--scheduled` + Task 5 Steps 1,5,6.

**Placeholder scan:** No TBD/TODO/"add error handling". The Task 1 Step 6 mock-URL caveat (codex M1) is now resolved inline — the test uses the verified `WP`/`AE` constants and `{AE}/find` route from `tests/test_wp_publish.py:4-16`.

**Codex audit (2026-05-24) folded in:** M1 (test mock URLs → real `{AE}/find`/`{WP}/posts` pattern, verified against source); H3 (corrected the false "TOC-exclusion" ordering rationale — `inject_toc` only scans `<h2>`); H1 (docstring "no partial state" → "no WP POST write"; orphaned-inline-media caveat noted); M2 (added `sync_status` prereq + `wp_post_id`/explicit-slug note to Task 5 Step 5); M3/M4/L3 (order-independent `_tag_attr` for canonical+meta; pixel exclusion widened to URL + visibility/opacity); L2 (reworded the JSON-LD adversarial comment — it was already adversarial, the explanation was backwards); L4 (missing-`url` guard); N1 (PowerShell verify command). Codex's core verdict — guards correct, ordering safe, demote-all is the right design, `republish.py` preserves scheduled date/status — required no logic changes.

**Type consistency:** `audit_html` returns `list[dict]` with keys `check/ok/detail/severity` — consumed identically in tests (`_result`) and in `_print`/`run`. `strip_body_h1(html)` and `assert_jsonld_valid(html, slug)` signatures match their call sites in `publish_article` and their imports in the tests. `_LDJSON` regex is identical in `wp_publish.py` (Task 2) and `audit_live.py` (Task 3) — intentional shared contract; both parse the rendered/embedded block the same way.

**Adversarial coverage (writing-plans delta — a no-op/buggy impl must fail a test):** Task1 `test_strip_body_h1_demotes_to_h2` (no-op leaves `<h1>` → fails) + integration `test_publish_demotes_body_h1` (unwired → fails). Task2 `test_assert_jsonld_valid_rejects_extra_data` (always-None stub → fails) using the *real* Outlook live-failure shape. Task3 `test_double_h1_fails` + `test_broken_jsonld_fails` (hardcoded ok=True stub → fails) using a production-shaped page fragment with the FB pixel.
