"""Rank all published/scheduled articles by improvement opportunity.

Usage:
  python -m scripts.triage trainingint
  python -m scripts.triage trainingint --top 5
  python -m scripts.triage trainingint --no-gsc
"""
import re, sys, json, pathlib, yaml
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTERNAL_LINK_RE = re.compile(
    r'href=["\'](?P<url>https?://www\.trainingint\.com/(?!\?)(?:[^"\']+))["\']',
    re.I,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load(site):
    cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())["sites"][site]
    budgets = yaml.safe_load((ROOT / "seo/audit-budgets.yaml").read_text())
    status_map = yaml.safe_load((ROOT / f"status/{site}.yaml").read_text()) or {}
    return cfg, budgets, status_map


def _get_html(slug, entry, content_root):
    """Return (html, is_live). Prefers live fetch for published; falls back to artifact."""
    from scripts.audit_live import fetch
    status = entry.get("status")
    url = entry.get("url", "")
    if status == "published" and url and "?p=" not in url:
        try:
            return fetch(url), True
        except Exception:
            pass
    art = content_root / slug / "_draft" / "04-seo.html"
    if art.exists():
        return art.read_text(encoding="utf-8"), False
    return "", False


def _audit_errors(html, is_live, url):
    from scripts.audit_live import audit_html, audit_artifact_html
    if not html:
        return [], 0
    checks = audit_html(html, expected_url=url) if is_live else audit_artifact_html(html)
    errors = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    return errors, len(errors)


def _count_internal_links(html, base_url):
    urls = {m.group("url") for m in INTERNAL_LINK_RE.finditer(html)
            if base_url in m.group("url")}
    return len(urls)


def _freshness_days(entry):
    li = entry.get("last_improved")
    if not li:
        return 365
    return max(0, (date.today() - date.fromisoformat(str(li))).days)


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


# ── scoring ───────────────────────────────────────────────────────────────────

def score_slug(slug, entry, cfg, budgets, gsc_page_data, content_root):
    base_url = cfg["base_url"]
    link_min = cfg.get("link_budget", {}).get("internal_sibling_min", 2)
    weights = budgets.get("triage_weights", {})
    w_audit = weights.get("audit", 3.0)
    w_link = weights.get("link_gap", 2.0)
    w_fresh = weights.get("freshness", 1.0)
    w_gsc = weights.get("gsc", 1.0)

    url = entry.get("url", "")
    html, is_live = _get_html(slug, entry, content_root)

    audit_errs, audit_count = _audit_errors(html, is_live, url)
    actual_links = _count_internal_links(html, base_url)
    link_gap = max(0, link_min - actual_links)
    fresh_days = _freshness_days(entry)
    opp = gsc_opportunity(gsc_page_data.get(url, []), weights)
    gsc_score, striking, hi_impr = opp["score"], opp["striking"], opp["ctr_capture"]

    score = (
        w_audit * audit_count +
        w_link * link_gap +
        w_fresh * (fresh_days / 30) +
        w_gsc * gsc_score
    )

    findings = []
    for c in audit_errs:
        findings.append(f"[audit] {c['check']}: {c['detail']}")
    if link_gap > 0:
        findings.append(f"[links] {actual_links} internal links (min {link_min}, gap={link_gap})")
    if entry.get("last_improved") is None:
        findings.append("[freshness] never improved")
    else:
        findings.append(f"[freshness] last improved {fresh_days}d ago")
    for q in striking[:3]:
        findings.append(
            f"[gsc] pos {q['position']:.1f}: \"{q['query']}\" "
            f"({q['impressions']} impr, {q['ctr']*100:.1f}% CTR)"
        )
    for q in hi_impr[:2]:
        if q not in striking:
            findings.append(
                f"[ctr-capture] pos {q['position']:.1f} \"{q['query']}\" "
                f"({q['impressions']} impr, {q['ctr']*100:.1f}% CTR) — title/meta fix"
            )

    return {
        "slug": slug,
        "status": entry.get("status"),
        "score": round(score, 2),
        "audit_errors": audit_count,
        "link_gap": link_gap,
        "freshness_days": fresh_days,
        "gsc_score": round(gsc_score, 2),
        "striking_count": len(striking),
        "ctr_capture": [
            f"pos {q['position']:.1f} \"{q['query']}\" ({q['impressions']} impr)"
            for q in hi_impr
        ],
        "findings": findings,
    }


# ── report ────────────────────────────────────────────────────────────────────

def _render_md(ranked, site, gsc_wired):
    today = date.today().isoformat()
    published = sum(1 for r in ranked if r["status"] == "published")
    scheduled = sum(1 for r in ranked if r["status"] == "scheduled")
    gsc_note = f"wired ({gsc_wired})" if gsc_wired else "absent (keyword dimension skipped)"
    lines = [
        f"# Triage: {site} — {today}",
        f"",
        f"{len(ranked)} articles scored ({published} published, {scheduled} scheduled)"
        f" | GSC: {gsc_note}",
        f"",
        f"## Ranked by Opportunity (worst first)",
        f"",
    ]
    for i, r in enumerate(ranked, 1):
        lines.append(
            f"### {i}. {r['slug']} [score: {r['score']}] — {r['status']}"
        )
        for f in r["findings"]:
            lines.append(f"  - {f}")
        lines.append("")
    capture = [r for r in ranked if r.get("ctr_capture")]
    if capture:
        lines += ["## CTR-capture quick wins (rank well, ~0 clicks — fix title/meta)", ""]
        for r in capture:
            lines.append(f"### {r['slug']} — {r['status']}")
            for c in r["ctr_capture"]:
                lines.append(f"  - {c}")
            lines.append("")
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def run(site, top=None, use_gsc=True):
    cfg, budgets, status_map = _load(site)
    content_root = ROOT / "content" / site
    gsc_property = cfg.get("gsc_property")

    gsc_page_data = {}
    if use_gsc and gsc_property:
        try:
            from scripts.gsc_client import fetch_all_page_queries
            print(f"Fetching GSC data for {gsc_property}…")
            gsc_page_data = fetch_all_page_queries(gsc_property)
            print(f"  {sum(len(v) for v in gsc_page_data.values())} query rows across "
                  f"{len(gsc_page_data)} pages")
        except Exception as e:
            print(f"  GSC unavailable ({e}) — keyword dimension skipped")

    candidates = {
        slug: entry for slug, entry in status_map.items()
        if entry.get("status") in ("published", "scheduled")
    }
    print(f"Scoring {len(candidates)} articles…")

    results = []
    for slug, entry in candidates.items():
        try:
            results.append(score_slug(slug, entry, cfg, budgets, gsc_page_data, content_root))
        except Exception as e:
            print(f"  [skip] {slug}: {e}")

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    if top:
        ranked = ranked[:top]

    today = date.today().isoformat()
    out_base = ROOT / "status" / f"triage-{site}-{today}"

    md = _render_md(ranked, site, gsc_property if gsc_page_data else None)
    out_base.with_suffix(".md").write_text(md, encoding="utf-8")

    machine = {"date": today, "site": site, "ranked": ranked}
    out_base.with_suffix(".json").write_text(
        json.dumps(machine, indent=2), encoding="utf-8"
    )

    print(f"\nWrote {out_base}.md and .json")
    print(f"\nTop {min(5, len(ranked))} by score:")
    for r in ranked[:5]:
        print(f"  {r['score']:6.1f}  [{r['status'][:3]}]  {r['slug']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    site = args[0] if args else "trainingint"
    top = None
    use_gsc = True
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top = int(args[i + 1])
        if a == "--no-gsc":
            use_gsc = False
    run(site, top=top, use_gsc=use_gsc)
