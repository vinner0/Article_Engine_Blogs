import responses, pytest
from scripts.lib.wp_client import WPClient
WP="https://www.trainingint.com/wp-json/wp/v2"
AE="https://www.trainingint.com/wp-json/ae/v1"
def c(): return WPClient(WP,"u","p")
@responses.activate
def test_find_uid_returns_id():
    responses.get(f"{AE}/find", json={"id":42}, status=200)
    assert c().find_post_by_uid("abc")==42
@responses.activate
def test_find_uid_404_is_none():
    responses.get(f"{AE}/find", status=404)
    assert c().find_post_by_uid("zzz") is None
@responses.activate
def test_find_uid_server_error_raises():           # I1: 5xx must propagate, not None
    responses.get(f"{AE}/find", status=500)
    with pytest.raises(Exception):
        c().find_post_by_uid("abc")
@responses.activate
def test_find_slug_none_when_empty():
    responses.get(f"{WP}/posts", json=[], status=200)
    assert c().find_post_by_slug("x") is None
@responses.activate
def test_find_slug_returns_id_when_found():         # C1: idempotency duplicate-guard
    responses.get(f"{WP}/posts", json=[{"id":7}], status=200)
    assert c().find_post_by_slug("existing-slug")==7
@responses.activate
def test_create_returns_id():
    responses.post(f"{WP}/posts", json={"id":99}, status=201)
    assert c().create_post({"title":"t","status":"draft"})==99
@responses.activate
def test_update_post_returns_id():                 # C2: idempotent re-run path
    responses.post(f"{WP}/posts/42", json={"id":42}, status=200)
    assert c().update_post(42, {"title":"x"})==42
@responses.activate
def test_read_post_meta_returns_value():           # C3a: probe-meta decision
    responses.get(f"{WP}/posts/5", json={"id":5,"meta":{"ae_content_uid":"uid1"}},
                  status=200)
    assert c().read_post_meta(5, "ae_content_uid")=="uid1"
@responses.activate
def test_read_post_meta_missing_key_returns_none():# C3b
    responses.get(f"{WP}/posts/5", json={"id":5,"meta":{}}, status=200)
    assert c().read_post_meta(5, "no_such_key") is None
@responses.activate
def test_me_returns_dict():                        # I5: probe rest_ok gate
    responses.get(f"{WP}/users/me", json={"id":1,"name":"u"}, status=200)
    assert c().me()["id"]==1
@responses.activate
def test_upload_media_returns_id():                # I2
    responses.post(f"{WP}/media", json={"id":55}, status=201)
    assert c().upload_media("h.jpg", b"\xff\xd8", "image/jpeg")==55
@responses.activate
def test_delete_post_sends_force():                # I2
    responses.delete(f"{WP}/posts/9", json={}, status=200)
    c().delete_post(9)
    assert "force=true" in responses.calls[-1].request.url.lower()
