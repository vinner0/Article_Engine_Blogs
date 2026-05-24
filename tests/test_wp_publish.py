import responses, pytest
from scripts.lib.wp_client import WPClient
from scripts.wp_publish import publish_article, content_uid, resolve_internal_links, push_meta_via_helper, resolve_inline_media, inject_toc, strip_body_h1
WP="https://www.trainingint.com/wp-json/wp/v2"; AE="https://www.trainingint.com/wp-json/ae/v1"
def wp(): return WPClient(WP,"u","p")

@responses.activate
def test_first_publish_creates_scheduled():
    responses.get(f"{AE}/find", status=404)            # uid not found
    responses.get(f"{WP}/posts", json=[], status=200)  # slug not found
    cr=responses.post(f"{WP}/posts", json={"id":100}, status=201)
    pid=publish_article(wp(),"uid1","how-to-x","How to X","<p>b</p>",{},
                        "2026-06-01T09:00:00",5,1)
    assert pid==100 and cr.call_count==1
    body=responses.calls[-1].request.body
    assert b'"future"' in body and b"2026-06-01T09:00:00" in body

@responses.activate
def test_rerun_same_uid_updates_not_duplicates():     # ADVERSARIAL: always-create stub fails
    responses.get(f"{AE}/find", json={"id":100}, status=200)   # uid FOUND
    cr=responses.post(f"{WP}/posts", json={"id":999}, status=201)
    up=responses.post(f"{WP}/posts/100", json={"id":100}, status=200)
    pid=publish_article(wp(),"uid1","how-to-x","How to X","<p>b</p>",{},
                        "2026-06-01T09:00:00",5,1)
    assert pid==100 and cr.call_count==0 and up.call_count==1

def test_resolve_internal_links_in_batch_vs_unresolved():
    html='See <a href="ae:sibling:how-to-y">Y</a> and <a href="ae:sibling:how-to-z">Z</a>.'
    status={"how-to-y":{"url":"https://www.trainingint.com/blog/how-to-y/"}}
    out,unresolved=resolve_internal_links(html,status)
    assert "https://www.trainingint.com/blog/how-to-y/" in out
    assert "ae:sibling:how-to-y" not in out
    assert "how-to-z" in unresolved and 'href="ae:sibling:how-to-z"' not in out  # left as plain text

@responses.activate
def test_push_meta_via_helper():
    h=responses.post(f"{AE}/meta/100", json={"ok":True,"id":100}, status=200)
    push_meta_via_helper(wp(),100,{"rank_math_title":"T"})
    assert h.call_count==1

@responses.activate
def test_resolve_inline_media_uploads_and_rewrites(tmp_path):  # spec §8.2 inline imgs
    (tmp_path/"hero.jpg").write_bytes(b"\xff\xd8jpeg")
    responses.post(f"{WP}/media", json={"id":55,
        "source_url":"https://www.trainingint.com/wp-content/uploads/hero.jpg"}, status=201)
    out=resolve_inline_media(wp(),
        '<img src="ae:img:hero.jpg" alt="x"> and <img src="ae:img:hero.jpg">',
        str(tmp_path))
    assert out.count("https://www.trainingint.com/wp-content/uploads/hero.jpg")==2
    assert "ae:img:" not in out

@responses.activate
def test_tags_included_when_passed():                          # spec §8.3 tags
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[], status=200)
    responses.post(f"{WP}/posts", json={"id":101}, status=201)
    publish_article(wp(),"u","s","T","<p>b</p>",{},
                     "2026-06-01T09:00:00",5,1, tags=[3,4])
    assert b'"tags"' in responses.calls[-1].request.body

def test_resolve_internal_links_same_slug_twice_and_nested():  # ADVERSARIAL §8.5: C1+C2
    html=('<p>Intro <a href="ae:sibling:how-to-z" class="x">Z one</a>.</p>'
          '<p>Later <a href="ae:sibling:how-to-z">\n  <strong>Z two</strong>\n</a>.</p>'
          '<a href="ae:sibling:how-to-y">Y</a>')
    status={"how-to-y":{"url":"https://t/blog/how-to-y/"}}
    out,unresolved=resolve_internal_links(html,status)
    assert "data-ae-unresolved" not in out       # pre-fix leaves >=1 (count=1 / no DOTALL)
    assert "ae:sibling:" not in out
    assert "<a " in out and 'href="https://t/blog/how-to-y/"' in out  # resolved still linked
    assert "Z one" in out and "Z two" in out                          # unresolved -> text
    assert unresolved.count("how-to-z")==2

@responses.activate
def test_publish_with_featured_media(tmp_path):                # B1: hero upload path
    (tmp_path/"hero.jpg").write_bytes(b"\xff\xd8jpeg")
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[], status=200)
    responses.post(f"{WP}/media", json={"id":77}, status=201)
    responses.post(f"{WP}/posts", json={"id":200}, status=201)
    pid=publish_article(wp(),"u","s","T","<p>b</p>",{}, "2026-06-01T09:00:00",5,1,
                        featured_path=str(tmp_path/"hero.jpg"))
    assert pid==200 and b'"featured_media"' in responses.calls[-1].request.body

@responses.activate
def test_publish_seo_meta_not_rest_writable_uses_helper():     # B2: §8.4 helper branch
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[], status=200)
    responses.post(f"{WP}/posts", json={"id":201}, status=201)
    h=responses.post(f"{AE}/meta/201", json={"ok":True,"id":201}, status=200)
    publish_article(wp(),"u","s","T","<p>b</p>",{"rank_math_title":"RT"},
                    "2026-06-01T09:00:00",5,1, seo_meta_rest_writable=False)
    bodies=[c.request.body for c in responses.calls
            if c.request.method=="POST" and c.request.url.startswith(f"{WP}/posts")]
    assert bodies and b'"rank_math_title"' not in bodies[0] and b'"ae_content_uid"' in bodies[0]
    assert h.call_count==1

@responses.activate
def test_publish_find_by_slug_fallback_updates():              # B3: uid-miss slug-hit
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[{"id":150}], status=200)
    cr=responses.post(f"{WP}/posts", json={"id":999}, status=201)
    up=responses.post(f"{WP}/posts/150", json={"id":150}, status=200)
    pid=publish_article(wp(),"u","existing-slug","T","<p>b</p>",{},
                        "2026-06-01T09:00:00",5,1)
    assert pid==150 and cr.call_count==0 and up.call_count==1

@responses.activate
def test_publish_threads_status_map_and_images_dir(tmp_path):  # B4: wired through publish
    (tmp_path/"a.jpg").write_bytes(b"\xff\xd8x")
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[], status=200)
    responses.post(f"{WP}/media", json={"id":9,
        "source_url":"https://www.trainingint.com/wp-content/uploads/a.jpg"}, status=201)
    responses.post(f"{WP}/posts", json={"id":300}, status=201)
    html='<a href="ae:sibling:sib">S</a> <img src="ae:img:a.jpg">'
    publish_article(wp(),"u","s","T",html,{}, "2026-06-01T09:00:00",5,1,
        status_map={"sib":{"url":"https://t/blog/sib/"}}, images_dir=str(tmp_path))
    body=responses.calls[-1].request.body
    assert b"https://t/blog/sib/" in body and b"wp-content/uploads/a.jpg" in body
    assert b"ae:sibling:" not in body and b"ae:img:" not in body

@responses.activate
def test_missing_inline_image_aborts_before_any_wp_write(tmp_path):  # B6: fail-clean
    responses.get(f"{AE}/find", status=404)
    cr=responses.post(f"{WP}/posts", json={"id":1}, status=201)
    with pytest.raises(FileNotFoundError):
        publish_article(wp(),"u","s","T",'<img src="ae:img:missing.jpg">',{},
            "2026-06-01T09:00:00",5,1, images_dir=str(tmp_path))
    assert cr.call_count==0     # no post created — no partial state

@responses.activate
def test_publish_aborts_on_residual_sibling_token():   # A1: fail-closed token gate
    # status_map omitted -> resolution skipped (the vlookup-leak path). The gate must
    # refuse rather than ship a raw href="ae:sibling:..." to a live post.
    cr=responses.post(f"{WP}/posts", json={"id":1}, status=201)
    with pytest.raises(ValueError, match="ae:sibling"):
        publish_article(wp(),"u","s","T",'<a href="ae:sibling:foo">F</a>',{},
            "2026-06-01T09:00:00",5,1)
    assert cr.call_count==0     # no WP write — gate runs before find/create

@responses.activate
def test_publish_aborts_on_residual_img_token():       # A1: gate also covers ae:img:
    # images_dir omitted -> inline media not resolved -> ae:img: would ship raw.
    cr=responses.post(f"{WP}/posts", json={"id":1}, status=201)
    with pytest.raises(ValueError, match="ae:img"):
        publish_article(wp(),"u","s","T",'<img src="ae:img:x.jpg">',{},
            "2026-06-01T09:00:00",5,1, status_map={})
    assert cr.call_count==0

def test_inject_toc_adds_nav_and_anchors():            # B6: publish-time TOC + H2 anchors
    html=('<h1>T</h1><p>intro</p>'
          '<h2>First Section</h2><p>a</p>'
          '<h2>Second Section</h2><p>b</p>'
          '<h2>Third Bit</h2><p>c</p>')
    out=inject_toc(html, min_h2=3)
    assert '<h2 id="first-section">First Section</h2>' in out
    assert '<h2 id="second-section">Second Section</h2>' in out
    assert 'class="ae-toc"' in out
    assert '#first-section' in out and '>First Section</a>' in out
    assert out.index('ae-toc') < out.index('id="first-section"')   # TOC sits before content

def test_inject_toc_skips_when_too_few_h2():           # short posts get no TOC
    html='<h1>T</h1><h2>Only One</h2><p>x</p>'
    assert inject_toc(html, min_h2=3)==html

def test_inject_toc_idempotent_and_unique_anchors():   # ADVERSARIAL: re-publish must not double
    html=('<h1>T</h1><p>i</p><h2>Same Name</h2><p>x</p>'
          '<h2>Same Name</h2><p>y</p><h2>Other</h2><p>z</p>')
    once=inject_toc(html, min_h2=3)
    assert once.count('class="ae-toc"')==1
    assert 'id="same-name"' in once and 'id="same-name-1"' in once  # collisions disambiguated
    assert inject_toc(once, min_h2=3)==once                          # second pass is a no-op

@responses.activate
def test_publish_injects_toc_into_long_post():         # B6: wired through publish
    responses.get(f"{AE}/find", status=404)
    responses.get(f"{WP}/posts", json=[], status=200)
    responses.post(f"{WP}/posts", json={"id":400}, status=201)
    html='<h1>T</h1><p>i</p><h2>Alpha</h2><p>a</p><h2>Beta</h2><p>b</p><h2>Gamma</h2><p>c</p>'
    publish_article(wp(),"u","s","T",html,{}, "2026-06-01T09:00:00",5,1, status_map={})
    body=responses.calls[-1].request.body            # body is JSON -> quotes are escaped
    assert b'ae-toc' in body and b'#alpha' in body and b'>Alpha</a>' in body

@responses.activate
def test_update_live_post_publishes_not_futures():     # A2: status/date-aware backfill
    # Re-publishing an already-live post must not downgrade it to a future-dated draft.
    responses.get(f"{AE}/find", json={"id":17434}, status=200)
    up=responses.post(f"{WP}/posts/17434", json={"id":17434}, status=200)
    publish_article(wp(),"u","s","T","<p>b</p>",{}, "2026-05-22T09:00:00",5,1,
                    status_map={}, wp_status="publish")
    body=responses.calls[-1].request.body
    assert b'"publish"' in body and b'"future"' not in body and up.call_count==1

def test_strip_body_h1_demotes_to_h2():          # core contract
    # production-shaped: real Outlook artifact body H1 (04-seo.html:54)
    html = ('<p>intro</p>'
            '<h1>How to Use Copilot in Outlook in 2026: A Practical Walkthrough</h1>'
            '<h2>Setup</h2><p>body</p>')
    out = strip_body_h1(html)
    assert '<h1' not in out and '</h1>' not in out          # ADVERSARIAL: no-op stub fails here
    assert ('<h2>How to Use Copilot in Outlook in 2026: A Practical Walkthrough</h2>'
            in out)
    assert '<h2>Setup</h2>' in out                          # untouched real h2 survives

def test_strip_body_h1_idempotent():
    html = '<h1>Title</h1><h2>x</h2>'
    once = strip_body_h1(html)
    assert strip_body_h1(once) == once                      # ADVERSARIAL: a global re-run must not corrupt

def test_strip_body_h1_preserves_h1_attributes():
    html = '<h1 class="lead" id="top">Title</h1>'
    out = strip_body_h1(html)
    assert out == '<h2 class="lead" id="top">Title</h2>'

def test_strip_body_h1_noop_when_no_body_h1():
    html = '<h2>only h2 here</h2><p>x</p>'                   # the 3 clean published pages
    assert strip_body_h1(html) == html

@responses.activate
def test_publish_demotes_body_h1():   # B: wired through publish, no double-H1 ships
    responses.get(f"{AE}/find", status=404)             # uid not found
    responses.get(f"{WP}/posts", json=[], status=200)   # slug not found
    responses.post(f"{WP}/posts", json={"id": 100}, status=201)
    publish_article(wp(), "uid1", "how-to-x", "Real Title",
                    "<h1>Real Title</h1><h2>A</h2><p>x</p>", {}, "2026-06-01T09:00:00", 5, 1)
    body = responses.calls[-1].request.body             # bytes of the create POST
    assert b"<h1" not in body          # ADVERSARIAL: drop the strip_body_h1 wiring line -> fails
    assert b"<h2>Real Title</h2>" in body
