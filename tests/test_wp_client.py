import responses
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
def test_find_slug_none_when_empty():
    responses.get(f"{WP}/posts", json=[], status=200)
    assert c().find_post_by_slug("x") is None
@responses.activate
def test_create_returns_id():
    responses.post(f"{WP}/posts", json={"id":99}, status=201)
    assert c().create_post({"title":"t","status":"draft"})==99
