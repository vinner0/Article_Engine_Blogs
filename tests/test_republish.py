import responses, pathlib
from scripts.lib.wp_client import WPClient
from scripts.republish import parse_seo_html, republish_slug
WP="https://www.trainingint.com/wp-json/wp/v2"; AE="https://www.trainingint.com/wp-json/ae/v1"
def wp(): return WPClient(WP,"u","p")

def test_parse_seo_html_splits_frontmatter_crlf():
    text='---\r\ntitle: "T"\r\ndescription: "D"\r\nheroImage: ae:img:hero.jpg\r\n---\r\n\r\n<h1>T</h1>'
    fm, body = parse_seo_html(text)
    assert fm["title"]=="T" and fm["description"]=="D" and fm["heroImage"]=="ae:img:hero.jpg"
    assert body.lstrip().startswith("<h1>") and "title:" not in body   # frontmatter stripped

def test_parse_seo_html_no_frontmatter_returns_body():
    fm, body = parse_seo_html("<h1>plain</h1>")
    assert fm=={} and body=="<h1>plain</h1>"

@responses.activate
def test_republish_slug_resolves_tokens_and_preserves_publish(tmp_path):
    art=tmp_path/"how-to-x"/"_draft"; art.mkdir(parents=True)
    (tmp_path/"how-to-x"/"images").mkdir()
    (tmp_path/"how-to-x"/"images"/"hero.jpg").write_bytes(b"\xff\xd8x")
    (art/"04-seo.html").write_text(
        '---\r\ntitle: "How to X"\r\ndescription: "Do X"\r\nheroImage: ae:img:hero.jpg\r\n---\r\n\r\n'
        '<h1>How to X</h1><p>See <a href="ae:sibling:sib">S</a></p><p><img src="ae:img:hero.jpg"></p>',
        encoding="utf-8")
    responses.get(f"{AE}/find", json={"id":17434}, status=200)
    responses.get(f"{WP}/posts/17434", json={"id":17434,"status":"publish","categories":[7],
        "author":2,"date":"2026-05-22T09:00:00+08:00","link":"https://t/x.html"}, status=200)
    responses.post(f"{WP}/media", json={"id":9,"source_url":"https://t/up/hero.jpg"}, status=201)
    responses.post(f"{WP}/posts/17434", json={"id":17434}, status=200)
    responses.post(f"{AE}/meta/17434", json={"ok":True}, status=200)
    sm={"how-to-x":{"wp_post_id":17434,"status":"published"},
        "sib":{"url":"https://t/sib.html"}}
    pid=republish_slug(wp(), "how-to-x", sm, tmp_path, default_cat=175, default_author=1)
    assert pid==17434
    upd=[c.request.body for c in responses.calls
         if c.request.method=="POST" and c.request.url.endswith("/posts/17434")][0]
    assert b"ae:sibling:" not in upd and b"ae:img:" not in upd     # tokens resolved (fail-closed gate would raise otherwise)
    assert b"t/sib.html" in upd                                    # sibling -> clean URL
    assert b'"publish"' in upd and b'"future"' not in upd          # live status preserved, not re-futured
