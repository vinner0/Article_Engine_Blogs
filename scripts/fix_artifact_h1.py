"""One-shot: demote body <h1> → <h2> in all 04-seo.html artifacts.

Mirrors strip_body_h1 in wp_publish.py (idempotent, non-destructive).
Run before scheduled posts go live to silence the body_h1_absent audit flag.

Usage:
  python -m scripts.fix_artifact_h1              # all sites in content/
  python -m scripts.fix_artifact_h1 trainingint  # single site
  python -m scripts.fix_artifact_h1 --dry-run    # show what would change
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
_H1 = re.compile(r'<(/?)h1(\b[^>]*)>', re.I)


def _fix(path, dry_run=False):
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        return False
    body = parts[2]
    new_body = _H1.sub(r'<\1h2\2>', body)
    if new_body == body:
        return False
    if not dry_run:
        path.write_text(parts[0] + "---\n" + parts[1] + "---\n" + new_body, encoding="utf-8")
    return True


def run(sites=None, dry_run=False):
    content_root = ROOT / "content"
    if sites:
        roots = [content_root / s for s in sites]
    else:
        roots = [d for d in content_root.iterdir() if d.is_dir()]

    changed = []
    for site_dir in sorted(roots):
        for f in sorted(site_dir.rglob("_draft/04-seo.html")):
            slug = f.parent.parent.name
            if _fix(f, dry_run=dry_run):
                changed.append(f"{site_dir.name}/{slug}")

    tag = "[DRY-RUN] " if dry_run else ""
    if changed:
        print(f"{tag}Fixed {len(changed)} file(s):")
        for s in changed:
            print(f"  {s}")
    else:
        print(f"{tag}No files needed fixing.")
    return changed


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry-run" in args
    sites_arg = [a for a in args if not a.startswith("--")]
    run(sites=sites_arg or None, dry_run=dry)
