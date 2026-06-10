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
