"""Pure logic for the staged-improvement review dashboard (scripts/review_server.py).

Discovers pending `_improve/` stagings, builds word-level before/after diffs, and
handles save/reject. Approve is delegated to scripts.apply_improvement.run.

Every function takes an explicit `root` so it is testable against a temp tree.
"""
from __future__ import annotations
import html
import shutil
import difflib
import pathlib
import re
import yaml

IMPROVE_REL = ("_improve", "04-seo.html")
DRAFT_REL = ("_draft", "04-seo.html")


def _status_map(root, site):
    p = pathlib.Path(root) / "status" / f"{site}.yaml"
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _base_url(root, site):
    p = pathlib.Path(root) / "config" / "sites.yaml"
    if not p.exists():
        return ""
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return (cfg.get("sites", {}).get(site, {}).get("base_url") or "").rstrip("/")


def list_pending(root, sites):
    """Every slug with a staged `_improve/04-seo.html`, newest-staged first, with meta."""
    root = pathlib.Path(root)
    out = []
    for site in sites:
        smap = _status_map(root, site)
        base = _base_url(root, site)
        site_dir = root / "content" / site
        if not site_dir.exists():
            continue
        for slug_dir in sorted(site_dir.iterdir()):
            improve = slug_dir.joinpath(*IMPROVE_REL)
            if not improve.exists():
                continue
            slug = slug_dir.name
            e = smap.get(slug) or {}
            pid = e.get("wp_post_id")
            out.append({
                "site": site,
                "slug": slug,
                "title": e.get("title", slug),
                "status": e.get("status", ""),
                "url": e.get("url", ""),
                "edit_url": f"{base}/wp-admin/post.php?post={pid}&action=edit" if pid else "",
                "scheduled_date": str(e.get("scheduled_date", "")),
                "mtime": improve.stat().st_mtime,
            })
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out


def read_pair(root, site, slug):
    """(before_text, after_text) = (_draft, _improve). Empty string if a side is missing."""
    d = pathlib.Path(root) / "content" / site / slug
    before = d.joinpath(*DRAFT_REL)
    after = d.joinpath(*IMPROVE_REL)
    bt = before.read_text(encoding="utf-8") if before.exists() else ""
    at = after.read_text(encoding="utf-8") if after.exists() else ""
    return bt, at


def save_improve(root, site, slug, text):
    """Write edited content back to the staged `_improve/04-seo.html`."""
    p = pathlib.Path(root) / "content" / site / slug / IMPROVE_REL[0] / IMPROVE_REL[1]
    if not p.parent.exists():
        raise FileNotFoundError(f"no _improve/ staging for {site}/{slug}")
    p.write_text(text.replace("\r\n", "\n"), encoding="utf-8")
    return p


def reject(root, site, slug):
    """Delete the `_improve/` staging dir. Returns True if something was removed."""
    d = pathlib.Path(root) / "content" / site / slug / IMPROVE_REL[0]
    if d.exists():
        shutil.rmtree(d)
        return True
    return False


def _body_lines(text):
    """Drop the YAML frontmatter block; return body lines for diffing."""
    if text.startswith("---"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            return parts[1].splitlines()
    return text.splitlines()


def _inline(before, after):
    """Word-level diff of two strings -> HTML with <del>/<ins> spans."""
    bw, aw = before.split(), after.split()
    sm = difflib.SequenceMatcher(None, bw, aw)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        b = html.escape(" ".join(bw[i1:i2]))
        a = html.escape(" ".join(aw[j1:j2]))
        if tag == "equal":
            out.append(a)
        elif tag == "replace":
            out.append(f"<del>{b}</del> <ins>{a}</ins>")
        elif tag == "delete":
            out.append(f"<del>{b}</del>")
        elif tag == "insert":
            out.append(f"<ins>{a}</ins>")
    return " ".join(x for x in out if x)


def diff_blocks(before_text, after_text):
    """Changed hunks only, each as a dict with rendered word-level `html` + raw before/after."""
    b, a = _body_lines(before_text), _body_lines(after_text)
    sm = difflib.SequenceMatcher(None, b, a)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        before_blk = "\n".join(b[i1:i2])
        after_blk = "\n".join(a[j1:j2])
        if tag == "replace":
            rendered = _inline(before_blk, after_blk)
        elif tag == "delete":
            rendered = f"<del>{html.escape(before_blk)}</del>"
        else:  # insert
            rendered = f"<ins>{html.escape(after_blk)}</ins>"
        blocks.append({"type": tag, "html": rendered, "before": before_blk, "after": after_blk})
    return blocks


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
