"""Reconcile status/<site>.yaml against WordPress reality. The engine publishes
future-dated posts but never polled WP afterward, so once a scheduled date passes
the YAML still says `scheduled` and carries no clean permalink (the vlookup drift).
This reads each tracked post's live status + permalink and writes them back, so
status is truthful and sibling resolution uses clean URLs (not ?p=NNN)."""
import os, sys, yaml, pathlib
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient
ROOT = pathlib.Path(__file__).resolve().parents[1]

_WP_TO_AE = {"publish": "published", "future": "scheduled", "draft": "draft"}

def reconcile_status(entry, wp_post):
    """Return a new entry with status mapped from the live WP status and url set to the
    live clean permalink. Pure; never mutates the input (it's a loaded-yaml dict)."""
    out = dict(entry)
    out["status"] = _WP_TO_AE.get(wp_post.get("status"), out.get("status"))
    if wp_post.get("link"):
        out["url"] = wp_post["link"]
    return out

def run(site="trainingint", apply=True):
    load_dotenv(ROOT / "credentials/.env")
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())
    s = cfg["sites"][site]
    pw = os.environ.get(s["app_password_env"]); user = os.environ.get(s["app_password_env"] + "_USER")
    if not pw or not user:
        sys.exit(f"Set {s['app_password_env']} and {s['app_password_env']}_USER in credentials/.env")
    wp = WPClient(s["wp_api_base"], user, pw)
    status_path = ROOT / f"status/{site}.yaml"
    status = yaml.safe_load(status_path.read_text()) or {}
    changes = []
    for slug, entry in status.items():
        pid = entry.get("wp_post_id")
        if not pid:
            continue
        try:
            post = wp.get_post(pid)
        except Exception as e:
            print(f"skip {slug} (post {pid}): {e}"); continue
        new = reconcile_status(entry, post)
        if new != entry:
            changes.append((slug, entry.get("status"), new.get("status"), new.get("url")))
            status[slug] = new
    for slug, old, new_st, url in changes:
        print(f"RECONCILE {slug}: {old} -> {new_st}  url={url}")
    if apply and changes:
        status_path.write_text(yaml.safe_dump(status, sort_keys=False))
        print(f"\nWROTE {status_path} ({len(changes)} entries updated)")
    else:
        print(f"\n{len(changes)} entries would change (dry-run)" if not apply
              else "\nno changes")
    return changes

if __name__ == "__main__":
    args = sys.argv[1:]
    apply = "--dry-run" not in args
    site = next((a for a in args if not a.startswith("--")), "trainingint")
    run(site, apply=apply)
