"""Emit JSON metadata for given slugs from status/<site>.yaml.

Read-only helper used by nightly_improve.ps1 to build rich completion emails
(PowerShell 5.1 has no YAML parser, so this stays in Python where yaml lives).

Usage: python -m scripts.slug_meta trainingint slug1 slug2 ...
Output: JSON object keyed by slug -> {title, url, edit_url, status, scheduled_date}
"""
import json, sys, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(site, slugs):
    status = yaml.safe_load((ROOT / f"status/{site}.yaml").read_text(encoding="utf-8")) or {}
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text(encoding="utf-8")) or {}
    base = (cfg.get("sites", {}).get(site, {}).get("base_url") or "").rstrip("/")

    out = {}
    for slug in slugs:
        e = status.get(slug) or {}
        pid = e.get("wp_post_id")
        out[slug] = {
            "title": e.get("title", slug),
            "url": e.get("url", ""),
            "edit_url": f"{base}/wp-admin/post.php?post={pid}&action=edit" if pid else "",
            "status": e.get("status", ""),
            "scheduled_date": str(e.get("scheduled_date", "")),
        }
    # ensure_ascii so the Windows console / PowerShell pipe never mojibakes
    print(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("Usage: python -m scripts.slug_meta <site> <slug> [slug...]")
    run(sys.argv[1], sys.argv[2:])
