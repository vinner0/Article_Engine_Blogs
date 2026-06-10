# Legacy Article Improvement — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make legacy WordPress posts first-class in the improvement engine, rank them by real GSC opportunity, and let Vinai approve changes against a rendered before/after preview.

**Architecture:** Three extensions to the existing engine. (1) `adopt_legacy.py` pulls published WP posts into the engine's `_draft/04-seo.html` + `status` artifact format so the existing `ae-5`/triage/dashboard loop applies unchanged. (2) `triage.py` gains real GSC signals (striking-distance, CTR-capture, clicks) so ranking stops being uniform-freshness. (3) the review dashboard renders before/after as side-by-side styled HTML on top of the existing word diff.

**Tech Stack:** Python 3, pytest 8, `responses` (HTTP mocking), PyYAML, Flask 3, requests. Run tests from project root: `python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-09-legacy-article-improvement-design.md` (Phase 1 = Components 1, 2, 3).

**Conventions observed in this codebase (do not deviate):**
- Artifact format: `"---\n" + <yaml frontmatter> + "---\n" + <html body>`. Frontmatter stripping splits on `"\n---\n"` (see `scripts/lib/review.py:_body_lines`).
- `status/<site>.yaml` is written with `yaml.dump(data, allow_unicode=True, sort_keys=True)` (see `scripts/apply_improvement.py:_save_status`).
- HTTP is mocked in tests with the `responses` library (see `tests/test_wp_client.py`).
- Pure logic takes an explicit `root` and is tested against `tmp_path` (see `scripts/lib/review.py`, `tests/test_review.py`).
- `tests/conftest.py` puts the repo root on `sys.path`; import as `from scripts.lib import x` / `from scripts import y`.

---

## Task 0: Quick wins (ops — no tests)

**Files:**
- Modify: Windows Task Scheduler env for `AE-NightlyImprove` (no repo file)
- Delete: `_tmp_seo_writer.py`

- [x] **Step 1: Bump nightly throughput to 3–4/day**

The nightly runner reads `AE_TOP_K` (default 2). Set it to 4 on the scheduled task (run in an elevated PowerShell):

```powershell
$action  = (Get-ScheduledTask -TaskName 'AE-NightlyImprove').Actions
schtasks /Change /TN "AE-NightlyImprove" /TR "powershell.exe -NonInteractive -File D:\VP\ARTICLE_ENGINE\scripts\nightly_improve.ps1" /F
[Environment]::SetEnvironmentVariable('AE_TOP_K','4','Machine')
```

Expected: `SUCCESS: The parameters of scheduled task "AE-NightlyImprove" have been changed.` Confirm: `[Environment]::GetEnvironmentVariable('AE_TOP_K','Machine')` prints `4`.

- [x] **Step 2: Remove the confirmed scratch script**

`_tmp_seo_writer.py` is a hardcoded single-article scratch (verified during scoping — not a module).

```bash
git rm _tmp_seo_writer.py
git commit -m "chore: remove _tmp_seo_writer.py scratch script"
```

Expected: one file deleted, commit created.

---

## Task 1: `WPClient.list_published_posts()` — enumerate legacy posts

**Files:**
- Modify: `scripts/lib/wp_client.py` (add method after `delete_post`)
- Test: `tests/test_wp_client.py` (append tests)

- [x] **Step 1: Write the failing tests**

Append to `tests/test_wp_client.py`:

```python
@responses.activate
def test_list_published_paginates_two_pages():     # collects across X-WP-TotalPages
    page1 = [{"id": 1, "slug": "a"}, {"id": 2, "slug": "b"}]
    page2 = [{"id": 3, "slug": "c"}]
    responses.get(f"{WP}/posts", json=page1, status=200,
                  headers={"X-WP-TotalPages": "2"})
    responses.get(f"{WP}/posts", json=page2, status=200,
                  headers={"X-WP-TotalPages": "2"})
    posts = c().list_published_posts(per_page=2)
    assert [p["id"] for p in posts] == [1, 2, 3]

@responses.activate
def test_list_published_single_page():
    responses.get(f"{WP}/posts", json=[{"id": 9, "slug": "z"}], status=200,
                  headers={"X-WP-TotalPages": "1"})
    assert [p["id"] for p in c().list_published_posts()] == [9]

@responses.activate
def test_list_published_empty():
    responses.get(f"{WP}/posts", json=[], status=200,
                  headers={"X-WP-TotalPages": "0"})
    assert c().list_published_posts() == []
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wp_client.py -k list_published -v`
Expected: FAIL — `AttributeError: 'WPClient' object has no attribute 'list_published_posts'`.

- [x] **Step 3: Implement the method**

In `scripts/lib/wp_client.py`, add this method to the `WPClient` class (after `delete_post`):

```python
    def list_published_posts(self, per_page=100):
        """All published posts (type=post), following X-WP-TotalPages pagination.

        Returns a list of raw post dicts (id, slug, link, title, content,
        modified, meta, acf when exposed). acf/meta may be absent depending on
        the site's REST config — callers must treat course_id as optional.
        """
        fields = "id,slug,link,title,content,modified,meta,acf"
        posts, page = [], 1
        while True:
            r = requests.get(
                f"{self.base}/posts",
                params={"status": "publish", "per_page": per_page,
                        "page": page, "_fields": fields},
                auth=self.auth, timeout=self.timeout,
            )
            if r.status_code == 400:        # past the last page
                break
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            posts.extend(batch)
            total_pages = int(r.headers.get("X-WP-TotalPages", page) or page)
            if page >= total_pages:
                break
            page += 1
        return posts
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wp_client.py -v`
Expected: PASS (all existing + 3 new).

- [x] **Step 5: Commit**

```bash
git add scripts/lib/wp_client.py tests/test_wp_client.py
git commit -m "feat(wp_client): list_published_posts with pagination"
```

---

## Task 2: `adopt_legacy` artifact + status builders (pure)

**Files:**
- Create: `scripts/adopt_legacy.py`
- Test: `tests/test_adopt_legacy.py`

- [x] **Step 1: Write the failing tests**

Create `tests/test_adopt_legacy.py`:

```python
"""Tests for legacy-post adoption (scripts/adopt_legacy.py)."""
import yaml
import pytest
from scripts import adopt_legacy as al

POST = {
    "id": 12345,
    "slug": "how-to-group-on-canva-tutorial",
    "link": "https://www.trainingint.com/how-to-group-on-canva-tutorial.html",
    "title": {"rendered": "How to Group on Canva"},
    "content": {"rendered": "<p>Select the items and press Ctrl+G.</p>"},
    "modified": "2024-03-01T10:00:00",
    "acf": {"course_id": 42},
}


def test_build_artifact_roundtrips_frontmatter_and_body():
    art = al.build_artifact("trainingint", POST)
    # frontmatter is parseable and carries the key fields
    assert art.startswith("---\n")
    fm_raw, body = art.split("\n---\n", 1)
    fm = yaml.safe_load(fm_raw.lstrip("-\n"))
    assert fm["slug"] == "how-to-group-on-canva-tutorial"
    assert fm["title"] == "How to Group on Canva"
    assert fm["source"] == "legacy"
    assert fm["wp_post_id"] == 12345
    # body is the post's rendered HTML, verbatim
    assert body.strip() == "<p>Select the items and press Ctrl+G.</p>"


def test_make_status_entry_tags_legacy_and_course_id():
    entry = al.make_status_entry(POST, "2026-06-09")
    assert entry["status"] == "published"
    assert entry["source"] == "legacy"
    assert entry["wp_post_id"] == 12345
    assert entry["adopted"] == "2026-06-09"
    assert entry["course_id"] == 42
    assert entry["url"] == POST["link"]


def test_make_status_entry_omits_course_id_when_absent():
    p = dict(POST); p.pop("acf")
    entry = al.make_status_entry(p, "2026-06-09")
    assert "course_id" not in entry


def test_adopt_one_writes_artifact_and_is_idempotent(tmp_path):
    status_map = {}
    wrote = al.adopt_one(tmp_path, "trainingint", POST, status_map, "2026-06-09")
    art = (tmp_path / "content" / "trainingint" /
           "how-to-group-on-canva-tutorial" / "_draft" / "04-seo.html")
    assert wrote is True
    assert art.exists()
    assert "how-to-group-on-canva-tutorial" in status_map
    # second call: slug already tracked -> skip, no overwrite
    art.write_text("SENTINEL", encoding="utf-8")
    wrote2 = al.adopt_one(tmp_path, "trainingint", POST, status_map, "2026-06-10")
    assert wrote2 is False
    assert art.read_text(encoding="utf-8") == "SENTINEL"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_adopt_legacy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.adopt_legacy'`.

- [x] **Step 3: Implement the builders**

Create `scripts/adopt_legacy.py`:

```python
"""Adopt legacy WordPress posts into the engine's artifact + status format.

A post that has no engine artifact cannot be improved by ae-5 (which diffs
against a local _draft/04-seo.html baseline). This module pulls a published
post's rendered HTML into that baseline and registers it in status/<site>.yaml
tagged `source: legacy`. After adoption a legacy post is indistinguishable from
an engine article, so triage/ae-5/the dashboard apply unchanged.

Usage:
  python -m scripts.adopt_legacy trainingint            # adopt all untracked
  python -m scripts.adopt_legacy trainingint --limit 20 # adopt the first 20
"""
import sys, pathlib, yaml
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]


def build_artifact(site, post):
    """Return a `04-seo.html` baseline string (frontmatter + body) for a WP post."""
    fm = {
        "title": post["title"]["rendered"],
        "slug": post["slug"],
        "site": site,
        "url": post.get("link", ""),
        "wp_post_id": post["id"],
        "source": "legacy",
    }
    cid = (post.get("acf") or {}).get("course_id")
    if cid:
        fm["course_id"] = cid
    body = post["content"]["rendered"]
    return "---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=True) + "---\n" + body


def make_status_entry(post, today):
    """Return a status/<site>.yaml entry dict for a legacy post."""
    entry = {
        "title": post["title"]["rendered"],
        "url": post.get("link", ""),
        "wp_post_id": post["id"],
        "status": "published",
        "source": "legacy",
        "adopted": today,
    }
    cid = (post.get("acf") or {}).get("course_id")
    if cid:
        entry["course_id"] = cid
    return entry


def adopt_one(root, site, post, status_map, today):
    """Write the baseline artifact + register the status entry. Idempotent.

    Returns True if adopted, False if the slug was already tracked (skipped).
    """
    slug = post["slug"]
    if slug in status_map:
        return False
    art_dir = pathlib.Path(root) / "content" / site / slug / "_draft"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "04-seo.html").write_text(build_artifact(site, post), encoding="utf-8")
    status_map[slug] = make_status_entry(post, today)
    return True
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_adopt_legacy.py -v`
Expected: PASS (4 tests).

- [x] **Step 5: Commit**

```bash
git add scripts/adopt_legacy.py tests/test_adopt_legacy.py
git commit -m "feat(adopt): legacy post artifact + status builders"
```

---

## Task 3: `adopt_legacy.run()` orchestration

**Files:**
- Modify: `scripts/adopt_legacy.py` (add `run` + `__main__`)
- Test: `tests/test_adopt_legacy.py` (append)

- [x] **Step 1: Write the failing test**

Append to `tests/test_adopt_legacy.py`:

```python
def _seed_project(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sites.yaml").write_text(
        "sites:\n  trainingint:\n"
        "    base_url: https://www.trainingint.com\n"
        "    wp_api_base: https://www.trainingint.com/wp-json/wp/v2\n"
        "    app_password_env: WP_TRAININGINT\n", encoding="utf-8")
    (tmp_path / "status").mkdir()
    # one engine-owned slug already tracked -> must NOT be re-adopted
    (tmp_path / "status" / "trainingint.yaml").write_text(
        yaml.dump({"how-to-use-canva": {"status": "scheduled", "wp_post_id": 17672}}),
        encoding="utf-8")


def test_run_adopts_only_untracked(tmp_path, monkeypatch):
    _seed_project(tmp_path)
    monkeypatch.setattr(al, "ROOT", tmp_path)
    fake_posts = [
        POST,                                                   # untracked -> adopt
        {"id": 17672, "slug": "how-to-use-canva",               # tracked -> skip
         "link": "x", "title": {"rendered": "Canva"},
         "content": {"rendered": "<p>hi</p>"}, "modified": "2024-01-01"},
    ]
    monkeypatch.setattr(al, "_fetch_posts", lambda site: fake_posts)

    adopted = al.run("trainingint")
    assert adopted == 1
    smap = yaml.safe_load((tmp_path / "status" / "trainingint.yaml").read_text())
    assert smap["how-to-group-on-canva-tutorial"]["source"] == "legacy"
    assert smap["how-to-use-canva"].get("source") != "legacy"  # tracked entry untouched
    assert (tmp_path / "content" / "trainingint" /
            "how-to-group-on-canva-tutorial" / "_draft" / "04-seo.html").exists()

    # idempotent: a second run adopts nothing new
    assert al.run("trainingint") == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adopt_legacy.py::test_run_adopts_only_untracked -v`
Expected: FAIL — `AttributeError: module 'scripts.adopt_legacy' has no attribute 'run'`.

- [x] **Step 3: Implement `run` + helpers**

Append to `scripts/adopt_legacy.py`:

```python
def _load(site):
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())["sites"][site]
    path = ROOT / "status" / f"{site}.yaml"
    status_map = (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}) or {}
    return cfg, status_map, path


def _fetch_posts(site):
    """Fetch all published posts via the WP REST client. Split out for testing."""
    import os
    from dotenv import load_dotenv
    from scripts.lib.wp_client import WPClient
    load_dotenv(ROOT / "credentials/.env")
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())["sites"][site]
    user = os.environ.get(cfg["app_password_env"] + "_USER")
    pw = os.environ.get(cfg["app_password_env"])
    if not user or not pw:
        raise RuntimeError(f"Missing {cfg['app_password_env']} credentials in .env")
    wp = WPClient(cfg["wp_api_base"], user, pw)
    return wp.list_published_posts()


def run(site, limit=None):
    """Adopt untracked published posts into status + artifacts. Returns count adopted."""
    _cfg, status_map, path = _load(site)
    today = date.today().isoformat()
    posts = _fetch_posts(site)

    adopted = 0
    for post in posts:
        if limit is not None and adopted >= limit:
            break
        if adopt_one(ROOT, site, post, status_map, today):
            adopted += 1
            print(f"  ADOPT {post['slug']} (post {post['id']})")

    if adopted:
        path.write_text(yaml.dump(status_map, allow_unicode=True, sort_keys=True),
                        encoding="utf-8")
    print(f"\nAdopted {adopted} legacy post(s) into status/{site}.yaml")
    return adopted


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("Usage: python -m scripts.adopt_legacy <site> [--limit N]")
    _site = args[0]
    _limit = None
    if "--limit" in args:
        _limit = int(args[args.index("--limit") + 1])
    run(_site, limit=_limit)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_adopt_legacy.py -v`
Expected: PASS (5 tests).

- [x] **Step 5: Commit**

```bash
git add scripts/adopt_legacy.py tests/test_adopt_legacy.py
git commit -m "feat(adopt): run() orchestration over WP REST, idempotent"
```

- [x] **Step 6: Manual smoke (real data, read-mostly)**

Run: `python -m scripts.adopt_legacy trainingint --limit 1`
Expected: prints `ADOPT <slug>` for one real legacy post; a new `content/trainingint/<slug>/_draft/04-seo.html` exists; `status/trainingint.yaml` has the new entry with `source: legacy`. Inspect the artifact body matches the live post. **Do not commit the adopted content/** (it's gitignored per `.gitignore`); commit only if status tracking is intended to be versioned — confirm with Vinai first.

---

## Task 4: GSC scoring rework in `triage.py`

**Files:**
- Modify: `seo/audit-budgets.yaml` (extend `triage_weights`)
- Modify: `scripts/triage.py` (replace `_gsc_signals`, update `score_slug`, `_render_md`)
- Test: `tests/test_triage.py` (create)

- [x] **Step 1: Extend the budgets config**

Replace the `triage_weights:` block in `seo/audit-budgets.yaml` (lines 24–30) with:

```yaml
# Triage scoring weights (triage.py)
# score = audit*errors + link_gap*gap + freshness*(days/30) + gsc*gsc_score
# gsc_score = gsc_striking*N_striking + gsc_ctr_gap*N_ctr_capture + gsc_clicks*sqrt(clicks)
triage_weights:
  audit: 3.0          # per failed error check
  link_gap: 2.0       # per missing internal sibling link
  freshness: 1.0      # multiplied by days_since_improved/30
  gsc: 1.0            # overall multiplier on gsc_score
  gsc_striking: 1.0   # per striking-distance query (pos 5-20)
  gsc_ctr_gap: 1.5    # per CTR-capture query (ranks well, ~0 clicks) — cheap wins
  gsc_clicks: 0.5     # multiplied by sqrt(total clicks) — reward proven demand
  striking_min_impr: 10   # min impressions to count a striking-distance query
  ctr_gap_min_impr: 50    # min impressions to count a CTR-capture query
  ctr_gap_max_ctr: 0.03   # CTR below this (at pos<=10) = capture failure
```

- [x] **Step 2: Write the failing tests**

Create `tests/test_triage.py`:

```python
"""Tests for triage GSC opportunity scoring (scripts/triage.py)."""
from scripts import triage

W = {
    "gsc_striking": 1.0, "gsc_ctr_gap": 1.5, "gsc_clicks": 0.5,
    "striking_min_impr": 10, "ctr_gap_min_impr": 50, "ctr_gap_max_ctr": 0.03,
}


def test_striking_distance_detected_and_sorted():
    rows = [
        {"query": "small", "position": 8.0, "impressions": 12, "ctr": 0.01, "clicks": 0},
        {"query": "big",   "position": 6.0, "impressions": 800, "ctr": 0.0, "clicks": 0},
        {"query": "toolow","position": 3.0, "impressions": 500, "ctr": 0.0, "clicks": 0},
        {"query": "weak",  "position": 7.0, "impressions": 5,   "ctr": 0.0, "clicks": 0},
    ]
    opp = triage.gsc_opportunity(rows, W)
    assert [r["query"] for r in opp["striking"]] == ["big", "small"]  # impr-sorted, threshold applied


def test_ctr_capture_detects_high_rank_zero_clicks():
    rows = [
        {"query": "ranks-no-clicks", "position": 1.1, "impressions": 1500, "ctr": 0.0, "clicks": 0},
        {"query": "ranks-fine",      "position": 2.0, "impressions": 200,  "ctr": 0.08, "clicks": 16},
        {"query": "too-few-impr",    "position": 1.0, "impressions": 10,   "ctr": 0.0, "clicks": 0},
    ]
    opp = triage.gsc_opportunity(rows, W)
    assert [r["query"] for r in opp["ctr_capture"]] == ["ranks-no-clicks"]


def test_score_rewards_clicks_and_differentiates():
    busy = triage.gsc_opportunity(
        [{"query": "q", "position": 6.0, "impressions": 800, "ctr": 0.0, "clicks": 36}], W)
    idle = triage.gsc_opportunity([], W)
    assert busy["score"] > idle["score"]      # not flat
    assert idle["score"] == 0


def test_empty_rows_is_zero_not_error():
    assert triage.gsc_opportunity([], W) == {
        "score": 0, "striking": [], "ctr_capture": [], "clicks_total": 0}
```

- [x] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_triage.py -v`
Expected: FAIL — `AttributeError: module 'scripts.triage' has no attribute 'gsc_opportunity'`.

- [x] **Step 4: Implement `gsc_opportunity` and wire it in**

In `scripts/triage.py`, **replace** `_gsc_signals` (lines 65–72) with:

```python
def gsc_opportunity(rows, weights):
    """Pure GSC opportunity scoring for one page's query rows.

    Returns {score, striking, ctr_capture, clicks_total}. `striking` and
    `ctr_capture` are impression-sorted (most impactful first).
    """
    if not rows:
        return {"score": 0, "striking": [], "ctr_capture": [], "clicks_total": 0}
    s_min = weights.get("striking_min_impr", 10)
    c_min = weights.get("ctr_gap_min_impr", 50)
    c_max = weights.get("ctr_gap_max_ctr", 0.03)
    striking = sorted(
        [r for r in rows if 5 <= r["position"] <= 20 and r["impressions"] >= s_min],
        key=lambda r: r["impressions"], reverse=True)
    ctr_capture = sorted(
        [r for r in rows if r["position"] <= 10 and r["impressions"] >= c_min and r["ctr"] < c_max],
        key=lambda r: r["impressions"], reverse=True)
    clicks_total = sum(r.get("clicks", 0) for r in rows)
    score = (weights.get("gsc_striking", 1.0) * len(striking)
             + weights.get("gsc_ctr_gap", 1.5) * len(ctr_capture)
             + weights.get("gsc_clicks", 0.5) * (clicks_total ** 0.5))
    return {"score": score, "striking": striking, "ctr_capture": ctr_capture,
            "clicks_total": clicks_total}
```

In `score_slug`, **replace** the GSC line (line 93):

```python
    gsc_score, striking, hi_impr = _gsc_signals(url, gsc_page_data)
```

with:

```python
    opp = gsc_opportunity(gsc_page_data.get(url, []), weights)
    gsc_score, striking, hi_impr = opp["score"], opp["striking"], opp["ctr_capture"]
```

In `score_slug`, **replace** the findings loop for `hi_impr` (lines 116–121) with the CTR-capture wording:

```python
    for q in hi_impr[:2]:
        if q not in striking:
            findings.append(
                f"[ctr-capture] pos {q['position']:.1f} \"{q['query']}\" "
                f"({q['impressions']} impr, {q['ctr']*100:.1f}% CTR) — title/meta fix"
            )
```

In `score_slug`'s returned dict (lines 123–133), add one key after `"striking_count"`:

```python
        "ctr_capture": [
            f"pos {q['position']:.1f} \"{q['query']}\" ({q['impressions']} impr)"
            for q in hi_impr
        ],
```

- [x] **Step 5: Add a CTR-capture shortlist to the report**

In `scripts/triage.py`, in `_render_md`, before `return "\n".join(lines)` (line 159), insert:

```python
    capture = [r for r in ranked if r.get("ctr_capture")]
    if capture:
        lines += ["## CTR-capture quick wins (rank well, ~0 clicks — fix title/meta)", ""]
        for r in capture:
            lines.append(f"### {r['slug']} — {r['status']}")
            for c in r["ctr_capture"]:
                lines.append(f"  - {c}")
            lines.append("")
```

- [x] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_triage.py tests/test_config.py -v`
Expected: PASS (triage tests + config test that loads `audit-budgets.yaml` still parses).

- [x] **Step 7: Commit**

```bash
git add scripts/triage.py seo/audit-budgets.yaml tests/test_triage.py
git commit -m "feat(triage): real GSC scoring (striking/CTR-capture/clicks) + shortlist"
```

---

## Task 5: Rendered side-by-side preview in the dashboard

**Files:**
- Modify: `scripts/lib/review.py` (add `body_html` + `resolve_preview`)
- Modify: `scripts/review_server.py` (add 2 routes + iframe panes)
- Test: `tests/test_review.py` (append)

- [x] **Step 1: Write the failing tests**

Append to `tests/test_review.py`:

```python
def test_body_html_strips_frontmatter():
    txt = "---\ntitle: x\n---\n<p>hello</p>\n<p>world</p>"
    assert review.body_html(txt) == "<p>hello</p>\n<p>world</p>"


def test_resolve_preview_rewrites_img_and_sibling():
    body = ('<img src="ae:img:hero.jpg" alt="h">'
            '<a href="ae:sibling:how-to-use-canva">canva</a>')
    smap = {"how-to-use-canva": {"url": "https://www.trainingint.com/how-to-use-canva.html"}}
    out = review.resolve_preview(body, "trainingint", "my-slug", smap)
    assert 'src="/img/trainingint/my-slug/hero.jpg"' in out
    assert 'href="https://www.trainingint.com/how-to-use-canva.html"' in out
    assert "ae:img:" not in out and "ae:sibling:" not in out


def test_resolve_preview_unknown_sibling_falls_back_to_hash():
    out = review.resolve_preview('<a href="ae:sibling:nope">x</a>', "trainingint", "s", {})
    assert 'href="#"' in out
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_review.py -k "body_html or resolve_preview" -v`
Expected: FAIL — `AttributeError: module 'scripts.lib.review' has no attribute 'body_html'`.

- [x] **Step 3: Implement the pure preview helpers**

In `scripts/lib/review.py`, add `import re` to the imports (line 8 area) and append at end of file:

```python
_IMG_RE = re.compile(r'ae:img:([A-Za-z0-9._\-]+)')
_SIB_RE = re.compile(r'ae:sibling:([A-Za-z0-9._\-]+)')


def body_html(text):
    """The HTML body with YAML frontmatter stripped, as one string."""
    return "\n".join(_body_lines(text))


def resolve_preview(body, site, slug, status_map):
    """Rewrite ae:img:/ae:sibling: placeholders to preview-servable URLs.

    ae:img:FILE   -> /img/<site>/<slug>/FILE  (served by the dashboard)
    ae:sibling:SL -> the sibling's live url from status_map, or '#' if unknown.
    """
    def _img(m):
        return f"/img/{site}/{slug}/{m.group(1)}"

    def _sib(m):
        return (status_map.get(m.group(1)) or {}).get("url") or "#"

    return _SIB_RE.sub(_sib, _IMG_RE.sub(_img, body))
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_review.py -v`
Expected: PASS (all existing + 3 new).

- [x] **Step 5: Commit the pure logic**

```bash
git add scripts/lib/review.py tests/test_review.py
git commit -m "feat(review): body_html + resolve_preview placeholder rewriting"
```

- [x] **Step 6: Wire the rendered panes into the server**

In `scripts/review_server.py`:

(a) add `send_from_directory` to the flask import (line 14):

```python
from flask import Flask, request, redirect, url_for, flash, render_template_string, send_from_directory
```

(b) add this CSS constant after `ROOT`/`SITES` (line 21):

```python
PREVIEW_CSS = (
    "<style>body{font:16px/1.6 Georgia,serif;max-width:720px;margin:16px auto;"
    "padding:0 18px;color:#222}img{max-width:100%;height:auto}h1,h2,h3{font-family:"
    "-apple-system,Segoe UI,sans-serif;line-height:1.25}.ae-course-card{font-family:"
    "-apple-system,Segoe UI,sans-serif}</style>"
)
```

(c) in the `.diff` card block of `PAGE`, immediately before `<div class="diff">` (line 63), insert the side-by-side panes:

```html
    <div class="panes" style="display:flex;gap:10px;margin:12px 0">
      <div style="flex:1">
        <div class="tag">before</div>
        <iframe src="{{ url_for('preview', site=p.site, slug=p.slug, which='before') }}"
                style="width:100%;height:520px;border:1px solid #ddd;border-radius:8px"></iframe>
      </div>
      <div style="flex:1">
        <div class="tag">after (proposed)</div>
        <iframe src="{{ url_for('preview', site=p.site, slug=p.slug, which='after') }}"
                style="width:100%;height:520px;border:1px solid #ddd;border-radius:8px"></iframe>
      </div>
    </div>
```

(d) add two routes after `index()` (line 104):

```python
@app.route("/preview/<site>/<slug>/<which>")
def preview(site, slug, which):
    rel = review.IMPROVE_REL if which == "after" else review.DRAFT_REL
    p = ROOT / "content" / site / slug / rel[0] / rel[1]
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    smap = review._status_map(ROOT, site)
    body = review.resolve_preview(review.body_html(text), site, slug, smap)
    return PREVIEW_CSS + body


@app.route("/img/<site>/<slug>/<path:filename>")
def preview_img(site, slug, filename):
    return send_from_directory(ROOT / "content" / site / slug / "images", filename)
```

- [x] **Step 7: Manual verification (server has no unit test by design)**

Pre-req: at least one slug has a staged `_improve/04-seo.html` (run `ae-5` or copy a `_draft` to `_improve` for a quick visual check). Then:

Run: `python -m scripts.review_server` and open `http://127.0.0.1:5001`.
Expected: each staged card shows **two rendered panes side by side** (before / after) with images resolving, plus the existing word-diff below. Confirm an `ae:img:` image loads (Network tab: `/img/...` returns 200) and a sibling link points at a real URL.

- [x] **Step 8: Commit**

```bash
git add scripts/review_server.py
git commit -m "feat(review): rendered side-by-side before/after preview panes"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phase 1 = Components 1–3):**
- Component 1 (legacy importer) → Tasks 1, 2, 3. ✓
- Component 2 (GSC scoring rework + CTR shortlist) → Task 4. ✓
- Component 3 (rendered side-by-side preview) → Task 5. ✓
- Quick wins (K=4, scratch deletion) → Task 0. ✓
- Data-model change (`source`/`course_id`/`adopted` in status) → Task 2 (`make_status_entry`). ✓

**Deferred to later plans (correctly out of Phase 1):** images in ae-5, course-date widget, CTR-capture *mode* (this plan only surfaces the shortlist), discovery, E-E-A-T, interlinking, multi-domain.

**Type consistency:** `gsc_opportunity` returns `{score, striking, ctr_capture, clicks_total}` — consumed with those exact keys in `score_slug` (Task 4 step 4). `adopt_one(root, site, post, status_map, today)` signature matches both its call in `run` and the test. `resolve_preview(body, site, slug, status_map)` matches the `preview` route call.

**Known residual risks (flagged in spec, not closed by this plan):**
- Legacy HTML round-trip fidelity on republish — **GATE RUN 2026-06-10 on `power-bi-conditional-formatting-a-complete-guide` (post 17084): PASSED only after two hand-fixes. Found two CONFIRMED blockers (see Phase-2 section below). DO NOT bulk-adopt-and-republish until both are fixed in `adopt_legacy`.**
- `course_id` ACF exposure on `post` type via REST — `build_artifact`/`make_status_entry` treat it as optional; if REST doesn't expose `acf`, course_id is simply absent (no failure).
- `content/` is gitignored — Task 3 Step 6 notes confirming with Vinai whether adopted status entries are committed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-09-legacy-improvement-phase1.md`.

---

## Phase-1 Execution Result (2026-06-10)

All 6 tasks shipped to `master` (commits `a8c779e`, `9f07e02`, `612fc9a`, `7d8d8ae`, `5645878`, `732b2bd`; Task 0 = User-level `AE_TOP_K=4` + scratch deletion). Full suite 149 passed; per-task spec+quality reviews + final integration review done. Live triage with real GSC ran (9,284 query rows / 48 articles) — scoring now differentiates (top 16.9 = the adopted legacy post, lifted by 3 striking-distance queries) instead of the flat 12.17.

**Legacy republish gate** (the pre-bulk-adoption check) was run end-to-end on `power-bi-conditional-formatting-a-complete-guide` (post 17084): adopt → ae-5 keyword retarget (`where is conditional formatting in power bi`, pos 14.8) → live republish. **Verified live: no duplicate, content + clean 7-entry TOC + preserved meta description, tracking aligned.** It only passed because two issues were hand-fixed mid-flight — these are the Phase-2 blockers below.

### Phase-2 BLOCKERS — fix in `adopt_legacy` before ANY bulk adoption

1. **`build_artifact` must capture SEO meta.** Adopted frontmatter has no `description`, so `republish_slug` (`desc = fm.get("description","")`) pushes an **empty `_yoast_wpseo_metadesc`** via the helper route and **blanks the live post's meta description**. Fix: read `post["yoast_head_json"]["description"]` (and the Yoast title) at adoption time and write `description:` into the artifact frontmatter. Add a test that build_artifact carries a non-empty description when the source post has one.
2. **Normalize legacy heading misuse on adoption.** Legacy posts use `<h2>` for FAQ questions (`<h2>Q: …`) and author bios (`<h2>AUTHOR…`); `wp_publish.inject_toc` then lists all of them, producing a junk on-page TOC (17 entries, 10 junk, on 17084). Fix: demote non-section `<h2>`→`<h3>` during adoption (or teach `inject_toc` to skip FAQ/author headings). Add a test asserting the adopted body has no `<h2>Q:`/`<h2>AUTHOR`.

### Phase-2 minor

- **Post-title vs Yoast-title conflation:** `publish_article` derives `_yoast_wpseo_title` from the single `fm["title"]`, so republish can't preserve a Yoast SEO title distinct from the post title (17084's " Tutorial" suffix was dropped). If adopted posts need a distinct SEO title, capture it separately and thread it through the publish path.
