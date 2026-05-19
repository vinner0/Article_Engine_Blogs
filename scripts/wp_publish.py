"""Idempotent scheduled-post publisher. find_post_by_uid hits the always-installed
helper route (Task 9), so a rerun never duplicates a post — verified live by
probe_uid_roundtrip (Task 10) before this is used."""
import re, hashlib, mimetypes, pathlib, requests

def content_uid(site, slug):
    return hashlib.sha1(f"{site}:{slug}".encode()).hexdigest()[:16]

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
    # turn any anchor we could not resolve into plain text (drop the <a> wrapper)
    for slug in set(unresolved):
        html=re.sub(r'<a [^>]*data-ae-unresolved="1"[^>]*>(.*?)</a>', r'\1', html, count=1)
    return html, unresolved

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
                    tags=None, images_dir=None):
    if status_map is not None:
        html, _ = resolve_internal_links(html, status_map)
    if images_dir is not None:
        html = resolve_inline_media(wp, html, images_dir)
    payload={"title":title,"slug":slug,"content":html,"status":"future",
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
