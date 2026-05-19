import responses
from scripts.lib.wp_client import WPClient
from scripts.probe import probe_meta_writable, probe_uid_roundtrip
WP="https://www.trainingint.com/wp-json/wp/v2"; AE="https://www.trainingint.com/wp-json/ae/v1"
def wp(): return WPClient(WP,"u","p")
@responses.activate
def test_meta_writable_true_on_match():
    responses.post(f"{WP}/posts", json={"id":7}, status=201)
    responses.post(f"{WP}/posts/7", json={"id":7}, status=200)
    responses.get(f"{WP}/posts/7", json={"id":7,"meta":{"rank_math_title":"TOK"}}, status=200)
    responses.delete(f"{WP}/posts/7", json={}, status=200)
    assert probe_meta_writable(wp(),"rank_math_title","TOK") is True
@responses.activate
def test_meta_writable_false_on_mismatch():   # ADVERSARIAL: hardcoded True fails
    responses.post(f"{WP}/posts", json={"id":8}, status=201)
    responses.post(f"{WP}/posts/8", json={"id":8}, status=200)
    responses.get(f"{WP}/posts/8", json={"id":8,"meta":{"rank_math_title":""}}, status=200)
    responses.delete(f"{WP}/posts/8", json={}, status=200)
    assert probe_meta_writable(wp(),"rank_math_title","TOK") is False
@responses.activate
def test_uid_roundtrip_false_when_find_misses():  # ADVERSARIAL: idempotency must be proven live
    responses.post(f"{WP}/posts", json={"id":9}, status=201)
    responses.get(f"{AE}/find", status=404)        # helper can't find what we just wrote
    responses.delete(f"{WP}/posts/9", json={}, status=200)
    assert probe_uid_roundtrip(wp()) is False
