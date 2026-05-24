"""Idempotent scheduled-post publisher. find_post_by_uid hits the always-installed
helper route (Task 9), so a rerun never duplicates a post — verified live by
probe_uid_roundtrip (Task 10) before this is used."""
import re, hashlib, mimetypes, pathlib, requests

def content_uid(site, slug):
    return hashlib.sha1(f"{site}:{slug}".encode()).hexdigest()[:16]

# Any ae:sibling:/ae:img: token that survives resolution. Matches the token whether
# it sits in href="..."/src="..." or leaked as bare text; stops at quote/bracket/space.
_AE_TOKEN = re.compile(r'ae:(?:sibling|img):[^\s"\'<>]+')

def resolve_internal_links(html, status_map):
    """Replace ae:sibling:<slug> hrefs with live URLs for siblings present in
    status_map; for siblings not yet live, strip the anchor to plain text and
    report them (NO autonomous edits to other posts — spec §8)."""
    unresolved=[]
    def repl(m):
        slug=m.group(1)
        info=status_map.get(slug)
        if info and info.get("url"):
            return f'href="{info["url"]}"'
        unresolved.append(slug)
        return 'data-ae-unresolved="1"'
    html=re.sub(r'href="ae:sibling:([^"]+)"', repl, html)
    # Drop EVERY unresolved anchor's <a> wrapper -> plain text. Global (not
    # count=1: the same slug can appear 2+ times) and DOTALL (anchor text may
    # span newlines / wrap <strong>). Never ship a broken href-less <a> (§8.5).
    html=re.sub(r'<a [^>]*data-ae-unresolved="1"[^>]*>(.*?)</a>', r'\1', html,
                flags=re.DOTALL)
    return html, unresolved

def _slugify(text):
    s = re.sub(r'<[^>]+>', '', text)              # strip inner tags
    s = re.sub(r'&[a-zA-Z]+;|&#\d+;', ' ', s)     # entities -> space
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s

def inject_toc(html, min_h2=3):
    """Add slug `id` anchors to every <h2> and insert a jumplink TOC before the first
    section, for posts with >= min_h2 headings. Deterministic and idempotent — re-running
    on already-processed HTML is a no-op (so backfill re-publishes never stack TOCs).
    Anchor collisions (duplicate heading text) are disambiguated with a numeric suffix."""
    if 'class="ae-toc"' in html:
        return html
    if len(re.findall(r'<h2[^>]*>', html)) < min_h2:
        return html
    items, seen = [], {}
    def add_id(m):
        attrs, inner = m.group('attrs'), m.group('inner')
        existing = re.search(r'id\s*=\s*"([^"]*)"', attrs)
        if existing:
            sid = existing.group(1)
        else:
            base = _slugify(inner) or 'section'
            n = seen.get(base, 0); seen[base] = n + 1
            sid = base if n == 0 else f'{base}-{n}'
            attrs = f'{attrs} id="{sid}"'
        label = re.sub(r'<[^>]+>', '', inner).strip()
        items.append((sid, label))
        return f'<h2{attrs}>{inner}</h2>'
    new_html = re.sub(r'<h2(?P<attrs>[^>]*)>(?P<inner>.*?)</h2>', add_id, html, flags=re.DOTALL)
    nav = ('<nav class="ae-toc" aria-label="Table of contents">'
           '<p><strong>On this page</strong></p><ul>'
           + ''.join(f'<li><a href="#{sid}">{label}</a></li>' for sid, label in items)
           + '</ul></nav>')
    idx = new_html.find('<h2')
    return new_html[:idx] + nav + new_html[idx:]

def strip_body_h1(html):
    """WordPress renders the post title as the page <h1>; any <h1> in the body is
    therefore a duplicate (checklist #9). Demote every body <h1> to <h2> — non-
    destructive (no content lost), deterministic, idempotent. Preserves the tag's
    attributes (class/id) by rewriting only the tag name. Order-independent vs
    inject_toc (which only scans <h2>); placed after the content transforms as the
    last pre-write content normalization."""
    return re.sub(r'<(/?)h1(\b[^>]*)>', r'<\1h2\2>', html, flags=re.I)

def upload_featured(wp, image_path):
    p=pathlib.Path(image_path)
    mime=mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return wp.upload_media(p.name, p.read_bytes(), mime)

def push_meta_via_helper(wp, post_id, meta):
    r=requests.post(f"{wp.ae_base}/meta/{post_id}", json={"meta":meta},
                    auth=wp.auth, timeout=wp.timeout)
    r.raise_for_status()

def resolve_inline_media(wp, html, images_dir):
    """Upload each `ae:img:<filename>` placeholder's local file from images_dir
    and rewrite its src to the live WP media source_url (spec §8.2 — inline
    images, not just the hero). Mirrors the ae:sibling: resolve pattern; uploads
    each distinct file once. Direct media POST (wp.upload_media returns the id,
    but an inline <img src> needs the URL)."""
    cache={}
    def repl(m):
        fn=m.group(1)
        if fn not in cache:
            p=pathlib.Path(images_dir)/fn
            mime=mimetypes.guess_type(p.name)[0] or "image/jpeg"
            r=requests.post(f"{wp.base}/media", data=p.read_bytes(),
                headers={"Content-Disposition":f'attachment; filename="{p.name}"',
                         "Content-Type":mime}, auth=wp.auth, timeout=wp.timeout)
            r.raise_for_status(); cache[fn]=r.json()["source_url"]
        return f'src="{cache[fn]}"'
    return re.sub(r'src="ae:img:([^"]+)"', repl, html)

def publish_article(wp, uid, slug, title, html, meta, scheduled_iso,
                    category_id, author_id, featured_path=None,
                    status_map=None, seo_meta_rest_writable=True,
                    tags=None, images_dir=None, wp_status="future", add_toc=True):
    if status_map is not None:
        html, _ = resolve_internal_links(html, status_map)
    if images_dir is not None:
        html = resolve_inline_media(wp, html, images_dir)
    if add_toc:
        html = inject_toc(html)
    html = strip_body_h1(html)   # WP supplies the page <h1> (title); demote any body <h1> (order vs inject_toc is irrelevant — it only scans <h2>)
    # Fail-closed: never push a post that still carries an unresolved ae: placeholder.
    # This is the guard that makes the vlookup raw-token leak impossible — it fires whether
    # resolution was skipped (status_map/images_dir omitted) or a token was malformed, and
    # runs BEFORE any WP write so a refusal leaves no partial state.
    residual = _AE_TOKEN.findall(html)
    if residual:
        raise ValueError(f"unresolved ae: placeholders, refusing to publish {slug!r}: "
                         f"{sorted(set(residual))}")
    payload={"title":title,"slug":slug,"content":html,"status":wp_status,
             "date":scheduled_iso,"categories":[category_id],"author":author_id,
             "meta":{**({} if not seo_meta_rest_writable else meta),
                     "ae_content_uid":uid}}
    if tags:
        payload["tags"]=tags
    if featured_path:
        payload["featured_media"]=upload_featured(wp, featured_path)
    existing=wp.find_post_by_uid(uid) or wp.find_post_by_slug(slug)
    pid=wp.update_post(existing,payload) if existing is not None else wp.create_post(payload)
    if not seo_meta_rest_writable and meta:
        push_meta_via_helper(wp, pid, meta)
    return pid
