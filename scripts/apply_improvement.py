"""Apply a staged ae-5 improvement to one or more articles.

Usage:
  python -m scripts.apply_improvement trainingint how-to-filter-data-in-excel-step-by-step
  python -m scripts.apply_improvement trainingint slug1 slug2 ...

For published slugs: copies _improve/04-seo.html → _draft/04-seo.html, then
re-publishes via republish.py.

For scheduled slugs: copies _improve/ → _draft/ only. ae-8 will publish the
improved version on the scheduled date — no immediate push.

Updates last_improved in status/<site>.yaml after a successful apply.
Cleans up _improve/ after applying.

Nothing auto-runs without an explicit slug argument.
"""
import shutil, sys, pathlib, yaml, io
from datetime import date

# Windows console (cp1252) can't render non-ASCII in print; force UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_status(site):
    path = ROOT / f"status/{site}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data, path


def _save_status(data, path):
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")


def apply_slug(site, slug, status_map, dry_run=False):
    entry = status_map.get(slug)
    if not entry:
        print(f"  FAIL {slug}: not in status/{site}.yaml")
        return False

    improve_src = ROOT / "content" / site / slug / "_improve" / "04-seo.html"
    draft_dst   = ROOT / "content" / site / slug / "_draft"  / "04-seo.html"

    if not improve_src.exists():
        print(f"  FAIL {slug}: no staged _improve/04-seo.html — run ae-5 first")
        return False

    if not draft_dst.parent.exists():
        print(f"  FAIL {slug}: _draft/ dir missing")
        return False

    article_status = entry.get("status", "")

    if dry_run:
        print(f"  DRY  {slug} [{article_status}]: would copy _improve → _draft"
              + (" + republish" if article_status == "published" else ""))
        return True

    # Copy improved file over draft
    shutil.copy2(improve_src, draft_dst)
    print(f"  COPY {slug}: _improve/04-seo.html -> _draft/04-seo.html")

    # Re-publish if live
    if article_status == "published":
        from scripts.republish import republish_slug, run as republish_run
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv(ROOT / "credentials/.env")
            import yaml as _yaml
            cfg = _yaml.safe_load((ROOT / "config/sites.yaml").read_text())
            s = cfg["sites"][site]
            from scripts.lib.wp_client import WPClient
            pw   = os.environ.get(s["app_password_env"])
            user = os.environ.get(s["app_password_env"] + "_USER")
            if not pw or not user:
                raise RuntimeError(f"Missing {s['app_password_env']} credentials in .env")
            wp = WPClient(s["wp_api_base"], user, pw)
            p = s["probe"]
            pid = republish_slug(wp, slug, status_map,
                                 ROOT / "content" / site,
                                 p.get("default_category_id", 175),
                                 p.get("default_author_id", 1))
            print(f"  PUSH {slug} → post {pid}")
        except Exception as e:
            print(f"  WARN {slug}: republish failed ({e}) — _draft updated but not live yet")

    # Update last_improved
    status_map[slug]["last_improved"] = date.today().isoformat()

    # Clean up _improve/
    improve_dir = improve_src.parent
    try:
        shutil.rmtree(improve_dir)
        print(f"  CLEAN {slug}: removed _improve/")
    except Exception as e:
        print(f"  WARN {slug}: could not clean _improve/: {e}")

    return True


def run(site, slugs, dry_run=False):
    status_map, status_path = _load_status(site)

    ok_count = 0
    for slug in slugs:
        if apply_slug(site, slug, status_map, dry_run=dry_run):
            ok_count += 1

    if not dry_run and ok_count > 0:
        _save_status(status_map, status_path)
        print(f"\nUpdated last_improved for {ok_count} slug(s) in status/{site}.yaml")

    print(f"\nDone: {ok_count}/{len(slugs)} applied" + (" (dry run)" if dry_run else ""))


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit("Usage: python -m scripts.apply_improvement <site> <slug> [slug...] [--dry-run]")

    dry = "--dry-run" in args
    filtered = [a for a in args if a != "--dry-run"]
    _site = filtered[0]
    _slugs = filtered[1:]

    if not _slugs:
        sys.exit("Provide at least one slug.")

    run(_site, _slugs, dry_run=dry)
