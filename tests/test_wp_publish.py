import responses, pytest
from scripts.lib.wp_client import WPClient
from scripts.wp_publish import publish_article, content_uid, resolve_internal_links, push_meta_via_helper, resolve_inline_media
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
