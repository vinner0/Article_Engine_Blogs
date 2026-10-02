"""Push in-article course-box copy (config/course_boxes.yaml) to the WP option the
helper plugin renders from, and tag each engine post with its course id (`ae_course`
meta). Idempotent; re-run after editing copy or adding articles.

  python -m scripts.course_box trainingint [--dry-run] [--copy-only]
"""
import os, sys, yaml, pathlib, requests
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient
ROOT = pathlib.Path(__file__).resolve().parents[1]
FIELDS = ("name", "pitch", "funding", "cta")

def build_boxes(copy, courses):
    """{course_id: {name,pitch,funding,cta,url}}; url comes from the course registry."""
    boxes = {}
    for co in courses:
        c = copy.get(co["id"])
        if not c:
            raise ValueError(f"no course-box copy for course '{co['id']}'")
        blank = [f for f in FIELDS if not str(c.get(f, "")).strip()]
        if blank:
            raise ValueError(f"course-box copy for '{co['id']}' has blank {', '.join(blank)}")
        boxes[co["id"]] = {**{f: c[f] for f in FIELDS}, "url": co["course_url"]}
    return boxes

def assignments(courses, status):
    """{wp_post_id: course_id} for engine (non-legacy) posts already in WordPress."""
    by_slug = {x["slug"]: co["id"] for co in courses for x in co.get("cluster", [])}
    return {e["wp_post_id"]: by_slug[s] for s, e in status.items()
            if s in by_slug and e.get("wp_post_id") and e.get("source") != "legacy"}

def run(site, apply=True, copy_only=False):
    load_dotenv(ROOT / "credentials/.env")
    s = yaml.safe_load((ROOT / "config/sites.yaml").read_text())["sites"][site]
    courses = yaml.safe_load((ROOT / f"courses/{site}.yaml").read_text(encoding="utf-8"))["courses"]
    copy = yaml.safe_load((ROOT / "config/course_boxes.yaml").read_text(encoding="utf-8"))[site]
    status = yaml.safe_load((ROOT / f"status/{site}.yaml").read_text(encoding="utf-8")) or {}
    boxes, assign = build_boxes(copy, courses), assignments(courses, status)
    print(f"{len(boxes)} course boxes, {len(assign)} posts to tag" + ("" if apply else " (dry-run)"))
    if not apply:
        return boxes, assign
    wp = WPClient(s["wp_api_base"], os.environ[s["app_password_env"] + "_USER"], os.environ[s["app_password_env"]])
    r = requests.post(f"{wp.ae_base}/course-boxes", json={"boxes": boxes}, auth=wp.auth, timeout=wp.timeout)
    r.raise_for_status(); print("copy pushed:", r.json())
    if copy_only:
        return boxes, assign
    for pid, cid in assign.items():
        requests.post(f"{wp.ae_base}/meta/{pid}", json={"meta": {"ae_course": cid}},
                      auth=wp.auth, timeout=wp.timeout).raise_for_status()
    print(f"tagged {len(assign)} posts")
    return boxes, assign

if __name__ == "__main__":
    a = sys.argv[1:]
    run(next((x for x in a if not x.startswith("--")), "trainingint"),
        apply="--dry-run" not in a, copy_only="--copy-only" in a)
