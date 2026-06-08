"""Tests for the review dashboard pure-logic module (scripts/lib/review.py)."""
import textwrap
import yaml
import pytest
from scripts.lib import review


def _make_tree(root, *, staged=True, draft_body="<p>old paragraph here</p>",
               improve_body="<p>new paragraph here</p>"):
    """Build a minimal project tree under `root` with one trainingint article."""
    (root / "config").mkdir()
    (root / "config" / "sites.yaml").write_text(
        "sites:\n  trainingint:\n    base_url: https://www.trainingint.com\n", encoding="utf-8")
    (root / "status").mkdir()
    (root / "status" / "trainingint.yaml").write_text(yaml.dump({
        "advanced-powerpoint-animation-techniques": {
            "title": "Advanced PowerPoint Animation Techniques",
            "status": "scheduled",
            "url": "https://www.trainingint.com/?p=17755",
            "wp_post_id": 17755,
            "scheduled_date": "2026-07-06T09:00:00+08:00",
        }
    }), encoding="utf-8")
    slug_dir = root / "content" / "trainingint" / "advanced-powerpoint-animation-techniques"
    (slug_dir / "_draft").mkdir(parents=True)
    fm = "---\ntitle: x\n---\n"
    (slug_dir / "_draft" / "04-seo.html").write_text(fm + draft_body + "\n", encoding="utf-8")
    if staged:
        (slug_dir / "_improve").mkdir()
        (slug_dir / "_improve" / "04-seo.html").write_text(fm + improve_body + "\n", encoding="utf-8")
    return slug_dir


def test_list_pending_finds_staged_with_meta(tmp_path):
    _make_tree(tmp_path)
    pending = review.list_pending(tmp_path, ["trainingint"])
    assert len(pending) == 1
    r = pending[0]
    assert r["slug"] == "advanced-powerpoint-animation-techniques"
    assert r["title"] == "Advanced PowerPoint Animation Techniques"
    assert r["status"] == "scheduled"
    assert r["edit_url"] == "https://www.trainingint.com/wp-admin/post.php?post=17755&action=edit"


def test_list_pending_empty_when_no_staging(tmp_path):
    _make_tree(tmp_path, staged=False)
    assert review.list_pending(tmp_path, ["trainingint"]) == []


def test_diff_blocks_detects_replace_with_word_level_highlight(tmp_path):
    blocks = review.diff_blocks(
        "---\nt: x\n---\n<p>the quick brown fox</p>",
        "---\nt: x\n---\n<p>the quick red fox</p>",
    )
    assert len(blocks) == 1
    assert blocks[0]["type"] == "replace"
    # word-level: only "brown"->"red" should be wrapped, not the whole line
    assert "<del>brown</del>" in blocks[0]["html"]
    assert "<ins>red</ins>" in blocks[0]["html"]
    assert "quick" in blocks[0]["html"] and "<del>quick" not in blocks[0]["html"]


def test_diff_blocks_detects_insert(tmp_path):
    blocks = review.diff_blocks(
        "---\nt: x\n---\n<p>one</p>\n<p>three</p>",
        "---\nt: x\n---\n<p>one</p>\n<p>two</p>\n<p>three</p>",
    )
    assert any(b["type"] == "insert" and "two" in b["after"] for b in blocks)


def test_diff_blocks_ignores_identical_frontmatter(tmp_path):
    # identical content -> no blocks even though frontmatter is present
    same = "---\ntitle: x\n---\n<p>same</p>"
    assert review.diff_blocks(same, same) == []


def test_save_improve_writes_back(tmp_path):
    _make_tree(tmp_path)
    review.save_improve(tmp_path, "trainingint",
                        "advanced-powerpoint-animation-techniques", "EDITED CONTENT")
    before, after = review.read_pair(tmp_path, "trainingint",
                                     "advanced-powerpoint-animation-techniques")
    assert after == "EDITED CONTENT"


def test_save_improve_raises_without_staging(tmp_path):
    _make_tree(tmp_path, staged=False)
    with pytest.raises(FileNotFoundError):
        review.save_improve(tmp_path, "trainingint",
                            "advanced-powerpoint-animation-techniques", "x")


def test_reject_removes_staging(tmp_path):
    _make_tree(tmp_path)
    assert review.reject(tmp_path, "trainingint", "advanced-powerpoint-animation-techniques") is True
    assert review.list_pending(tmp_path, ["trainingint"]) == []
    # second reject is a no-op
    assert review.reject(tmp_path, "trainingint", "advanced-powerpoint-animation-techniques") is False
