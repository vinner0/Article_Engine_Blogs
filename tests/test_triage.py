"""Tests for triage GSC opportunity scoring (scripts/triage.py)."""
from scripts import triage

W = {
    "gsc_striking": 1.0, "gsc_ctr_gap": 1.5, "gsc_clicks": 0.5,
    "striking_min_impr": 10, "ctr_gap_min_impr": 50, "ctr_gap_max_ctr": 0.03,
}


def test_striking_distance_detected_and_sorted():
    rows = [
        {"query": "small", "position": 8.0, "impressions": 12, "ctr": 0.01, "clicks": 0},
        {"query": "big",   "position": 6.0, "impressions": 800, "ctr": 0.0, "clicks": 0},
        {"query": "toolow","position": 3.0, "impressions": 500, "ctr": 0.0, "clicks": 0},
        {"query": "weak",  "position": 7.0, "impressions": 5,   "ctr": 0.0, "clicks": 0},
    ]
    opp = triage.gsc_opportunity(rows, W)
    assert [r["query"] for r in opp["striking"]] == ["big", "small"]  # impr-sorted, threshold applied


def test_ctr_capture_detects_high_rank_zero_clicks():
    rows = [
        {"query": "ranks-no-clicks", "position": 1.1, "impressions": 1500, "ctr": 0.0, "clicks": 0},
        {"query": "ranks-fine",      "position": 2.0, "impressions": 200,  "ctr": 0.08, "clicks": 16},
        {"query": "too-few-impr",    "position": 1.0, "impressions": 10,   "ctr": 0.0, "clicks": 0},
    ]
    opp = triage.gsc_opportunity(rows, W)
    assert [r["query"] for r in opp["ctr_capture"]] == ["ranks-no-clicks"]


def test_score_rewards_clicks_and_differentiates():
    busy = triage.gsc_opportunity(
        [{"query": "q", "position": 6.0, "impressions": 800, "ctr": 0.0, "clicks": 36}], W)
    idle = triage.gsc_opportunity([], W)
    assert busy["score"] > idle["score"]      # not flat
    assert idle["score"] == 0


def test_empty_rows_is_zero_not_error():
    assert triage.gsc_opportunity([], W) == {
        "score": 0, "striking": [], "ctr_capture": [], "clicks_total": 0}
