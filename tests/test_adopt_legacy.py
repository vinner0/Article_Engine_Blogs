"""Tests for legacy-post adoption (scripts/adopt_legacy.py)."""
import yaml
import pytest
from scripts import adopt_legacy as al

POST = {
    "id": 12345,
    "slug": "how-to-group-on-canva-tutorial",
    "link": "https://www.trainingint.com/how-to-group-on-canva-tutorial.html",
    "title": {"rendered": "How to Group on Canva"},
    "content": {"rendered": "<p>Select the items and press Ctrl+G.</p>"},
    "modified": "2024-03-01T10:00:00",
    "acf": {"course_id": 42},
}


def test_build_artifact_roundtrips_frontmatter_and_body():
    art = al.build_artifact("trainingint", POST)
    # frontmatter is parseable and carries the key fields
    assert art.startswith("---\n")
    fm_raw, body = art.split("\n---\n", 1)
    fm = yaml.safe_load(fm_raw.lstrip("-\n"))
    assert fm["slug"] == "how-to-group-on-canva-tutorial"
    assert fm["title"] == "How to Group on Canva"
    assert fm["source"] == "legacy"
    assert fm["wp_post_id"] == 12345
    # body is the post's rendered HTML, verbatim
    assert body.strip() == "<p>Select the items and press Ctrl+G.</p>"


def test_make_status_entry_tags_legacy_and_course_id():
    entry = al.make_status_entry(POST, "2026-06-09")
    assert entry["status"] == "published"
    assert entry["source"] == "legacy"
    assert entry["wp_post_id"] == 12345
    assert entry["adopted"] == "2026-06-09"
    assert entry["course_id"] == 42
    assert entry["url"] == POST["link"]


def test_make_status_entry_omits_course_id_when_absent():
    p = dict(POST); p.pop("acf")
    entry = al.make_status_entry(p, "2026-06-09")
    assert "course_id" not in entry


def test_adopt_one_writes_artifact_and_is_idempotent(tmp_path):
    status_map = {}
    wrote = al.adopt_one(tmp_path, "trainingint", POST, status_map, "2026-06-09")
    art = (tmp_path / "content" / "trainingint" /
           "how-to-group-on-canva-tutorial" / "_draft" / "04-seo.html")
    assert wrote is True
    assert art.exists()
    assert "how-to-group-on-canva-tutorial" in status_map
    # second call: slug already tracked -> skip, no overwrite
    art.write_text("SENTINEL", encoding="utf-8")
    wrote2 = al.adopt_one(tmp_path, "trainingint", POST, status_map, "2026-06-10")
    assert wrote2 is False
    assert art.read_text(encoding="utf-8") == "SENTINEL"
