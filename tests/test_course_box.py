import pytest
from scripts.course_box import build_boxes, assignments

COURSES = [{"id": "excel", "course_url": "https://t.test/excel",
            "cluster": [{"slug": "how-to-filter"}, {"slug": "how-to-sumif"}]},
           {"id": "canva", "course_url": "https://t.test/canva", "cluster": [{"slug": "canva-101"}]}]
COPY = {"excel": {"name": "Excel", "pitch": "p", "funding": "f", "cta": "c"},
        "canva": {"name": "Canva", "pitch": "p", "funding": "f", "cta": "c"}}

def test_boxes_take_url_from_course_registry():
    b = build_boxes(COPY, COURSES)
    assert b["excel"]["url"] == "https://t.test/excel" and b["canva"]["name"] == "Canva"

def test_missing_copy_for_a_course_fails_loudly():   # ADVERSARIAL: a course must never render a half-empty box
    with pytest.raises(ValueError, match="canva"):
        build_boxes({"excel": COPY["excel"]}, COURSES)

def test_blank_field_fails_loudly():
    with pytest.raises(ValueError, match="excel.*cta"):
        build_boxes({**COPY, "excel": {**COPY["excel"], "cta": " "}}, COURSES)

def test_assignments_map_post_ids_to_course():
    status = {"how-to-filter": {"wp_post_id": 11}, "canva-101": {"wp_post_id": 12},
              "how-to-sumif": {}}                                   # not pushed yet -> skipped
    assert assignments(COURSES, status) == {11: "excel", 12: "canva"}

def test_legacy_posts_are_not_assigned():           # ADVERSARIAL: legacy posts keep their own CTAs
    status = {"how-to-filter": {"wp_post_id": 11, "source": "legacy"}}
    assert assignments(COURSES, status) == {}
