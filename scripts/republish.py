"""Minimal idempotent re-publish of already-published posts (SEO audit 2026-05-24
backfill). Re-runs the FIXED publish pipeline over existing posts so the live HTML
gets: ae:sibling/ae:img tokens resolved (kills the raw-token leak), a jumplink TOC,
and clean sibling URLs. Preserves each post's existing category / author / date /
status — this is a content refresh, not a re-schedule. Run sync_status FIRST so the
status map carries clean sibling permalinks.

Usage:  python -m scripts.republish trainingint how-to-use-vlookup-and-xlookup-in-excel [more-slugs...]
        (no slugs => every entry whose status is 'published')
Note: re-uploads inline/featured media each run (no media dedup) — fine for one-time backfill."""
import os, re, sys, yaml, pathlib
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient
from scripts.wp_publish import publish_article, content_uid
ROOT = pathlib.Path(__file__).resolve().parents[1]

def parse_seo_html(text):
    """Split YAML frontmatter (CRLF or LF) from the HTML body. Returns (dict, body)."""
    m = re.match(r'^﻿?---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$', text, re.DOTALL)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)

def republish_slug(wp, slug, status_map, content_root, default_cat, default_author):
    art = pathlib.Path(content_root) / slug
    fm, body = parse_seo_html((art / "_draft" / "04-seo.html").read_text(encoding="utf-8"))
    title = fm["title"]; desc = fm.get("description", "")
    hero = (fm.get("heroImage") or fm.get("hero_image") or "").replace("ae:img:", "")
    images_dir = art / "images"
    featured = str(images_dir / hero) if hero and (images_dir / hero).exists() else None
    entry = status_map[slug]
    post = wp.get_post(entry["wp_post_id"])           # preserve existing taxonomy/date/status
    cat = (post.get("categories") or [default_cat])[0]
    author = post.get("author", default_author)
    return publish_article(
        wp, content_uid("trainingint", slug), slug, title, body,
        {"_yoast_wpseo_title": title, "_yoast_wpseo_metadesc": desc},
        scheduled_iso=post.get("date"), category_id=cat, author_id=author,
        featured_path=featured, status_map=status_map, seo_meta_rest_writable=False,
        images_dir=str(images_dir), wp_status=post.get("status", "publish"))

def run(site="trainingint", slugs=None):
    load_dotenv(ROOT / "credentials/.env")
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())
    s = cfg["sites"][site]; p = s["probe"]
    pw = os.environ.get(s["app_password_env"]); user = os.environ.get(s["app_password_env"] + "_USER")
    if not pw or not user:
        sys.exit(f"Set {s['app_password_env']} and {s['app_password_env']}_USER in credentials/.env")
    wp = WPClient(s["wp_api_base"], user, pw)
    status_map = yaml.safe_load((ROOT / f"status/{site}.yaml").read_text()) or {}
    content_root = ROOT / "content" / site
    if not slugs:
        slugs = [k for k, v in status_map.items() if v.get("status") == "published"]
    print(f"Re-publishing {len(slugs)} post(s): {slugs}\n")
    for slug in slugs:
        try:
            pid = republish_slug(wp, slug, status_map, content_root,
                                 p.get("default_category_id", 175), p.get("default_author_id", 1))
            print(f"  OK  {slug} -> post {pid}")
        except Exception as e:
            print(f"  FAIL {slug}: {type(e).__name__}: {e}")

if __name__ == "__main__":
    args = sys.argv[1:]
    site = args[0] if args and not args[0].startswith("how-") else "trainingint"
    slug_args = [a for a in args if a != site]
    run(site, slug_args or None)
