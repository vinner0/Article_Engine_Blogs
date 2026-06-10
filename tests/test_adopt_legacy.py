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


def _seed_project(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sites.yaml").write_text(
        "sites:\n  trainingint:\n"
        "    base_url: https://www.trainingint.com\n"
        "    wp_api_base: https://www.trainingint.com/wp-json/wp/v2\n"
        "    app_password_env: WP_TRAININGINT\n", encoding="utf-8")
    (tmp_path / "status").mkdir()
    # one engine-owned slug already tracked -> must NOT be re-adopted
    (tmp_path / "status" / "trainingint.yaml").write_text(
        yaml.dump({"how-to-use-canva": {"status": "scheduled", "wp_post_id": 17672}}),
        encoding="utf-8")


def test_run_adopts_only_untracked(tmp_path, monkeypatch):
    _seed_project(tmp_path)
    monkeypatch.setattr(al, "ROOT", tmp_path)
    fake_posts = [
        POST,                                                   # untracked -> adopt
        {"id": 17672, "slug": "how-to-use-canva",               # tracked -> skip
         "link": "x", "title": {"rendered": "Canva"},
         "content": {"rendered": "<p>hi</p>"}, "modified": "2024-01-01"},
    ]
    monkeypatch.setattr(al, "_fetch_posts", lambda site: fake_posts)

    adopted = al.run("trainingint")
    assert adopted == 1
    smap = yaml.safe_load((tmp_path / "status" / "trainingint.yaml").read_text())
    assert smap["how-to-group-on-canva-tutorial"]["source"] == "legacy"
    assert smap["how-to-use-canva"].get("source") != "legacy"  # tracked entry untouched
    assert (tmp_path / "content" / "trainingint" /
            "how-to-group-on-canva-tutorial" / "_draft" / "04-seo.html").exists()

    # idempotent: a second run adopts nothing new
    assert al.run("trainingint") == 0
