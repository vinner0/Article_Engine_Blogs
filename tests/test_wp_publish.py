import responses
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
