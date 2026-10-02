"""Publish scheduled posts whose date has passed but WordPress never published
("missed schedule" — trainingint's pseudo-cron dropped 5 posts in Jul 2026), and
report the scheduled-queue runway. Called first thing by nightly_improve.ps1.

Prints machine lines the nightly parses:
  [rescued] <slug> <link>
  [runway] <days> <future_count>
"""
import os, sys, yaml, pathlib
from datetime import datetime, timezone
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient
ROOT = pathlib.Path(__file__).resolve().parents[1]

def _due(post):
    return datetime.fromisoformat(post["date_gmt"]).replace(tzinfo=timezone.utc)

def missed_posts(posts, now):
    """Future posts whose scheduled time is now or past."""
    return [p for p in posts if _due(p) <= now]

def runway_days(posts, now):
    """Whole days until the last still-pending scheduled post; 0 if none pending."""
    pending = [_due(p) for p in posts if _due(p) > now]
    return (max(pending) - now).days if pending else 0

def run(site="trainingint", apply=True):
    load_dotenv(ROOT / "credentials/.env")
    s = yaml.safe_load((ROOT / "config/sites.yaml").read_text())["sites"][site]
    pw = os.environ.get(s["app_password_env"]); user = os.environ.get(s["app_password_env"] + "_USER")
    if not pw or not user:
        sys.exit(f"Set {s['app_password_env']} and {s['app_password_env']}_USER in credentials/.env")
    wp = WPClient(s["wp_api_base"], user, pw)
    now = datetime.now(timezone.utc)
    future = wp.list_future_posts()
    for p in missed_posts(future, now):
        if apply:
            # Re-date to now so the post isn't buried under a weeks-old date.
            wp.update_post(p["id"], {"status": "publish", "date_gmt": now.strftime("%Y-%m-%dT%H:%M:%S")})
        print(f"[rescued] {p['slug']} {p.get('link','')}" + ("" if apply else " (dry-run)"))
    print(f"[runway] {runway_days(future, now)} {len(future) - len(missed_posts(future, now))}")

if __name__ == "__main__":
    args = sys.argv[1:]
    run(next((a for a in args if not a.startswith("--")), "trainingint"), apply="--dry-run" not in args)
