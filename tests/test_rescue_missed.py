from datetime import datetime, timezone
import responses
from scripts.rescue_missed import missed_posts, runway_days
from scripts.lib.wp_client import WPClient
WP="https://www.trainingint.com/wp-json/wp/v2"
NOW=datetime(2026,10,2,1,0,tzinfo=timezone.utc)   # 09:00 SGT

def p(pid, date_gmt): return {"id":pid,"slug":f"s{pid}","date_gmt":date_gmt}

def test_past_due_future_post_is_missed():
    assert [x["id"] for x in missed_posts([p(1,"2026-07-17T01:00:00")],NOW)]==[1]

def test_not_yet_due_is_left_alone():
    assert missed_posts([p(2,"2026-10-03T22:00:00")],NOW)==[]

def test_due_exactly_now_counts_as_missed():
    assert len(missed_posts([p(3,"2026-10-02T01:00:00")],NOW))==1

def test_runway_is_days_to_last_scheduled():
    assert runway_days([p(1,"2026-10-05T01:00:00"),p(2,"2026-10-13T22:00:00")],NOW)==11

def test_runway_ignores_already_missed_posts():   # ADVERSARIAL: stuck July posts must not look like runway
    assert runway_days([p(1,"2026-07-17T01:00:00")],NOW)==0

def test_runway_empty_queue_is_zero():
    assert runway_days([],NOW)==0

@responses.activate
def test_list_future_posts_queries_future_status():
    responses.get(f"{WP}/posts", json=[{"id":9,"slug":"x","date_gmt":"2026-10-05T01:00:00"}], status=200)
    out=WPClient(WP,"u","p").list_future_posts()
    assert out[0]["id"]==9
    assert "status=future" in responses.calls[0].request.url
