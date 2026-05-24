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
