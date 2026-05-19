import yaml, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
def test_sites_yaml_shape():
    s = yaml.safe_load((ROOT/"config/sites.yaml").read_text())["sites"]["trainingint"]
    assert s["wp_api_base"].endswith("/wp-json/wp/v2")
    assert s["app_password_env"] == "WP_TRAININGINT"
    assert "link_budget" in s and "probe" in s
    for k in ("rest_ok","seo_meta_rest_writable","uid_roundtrip_ok",
              "seo_plugin_emits_graph","default_category_id","default_author_id",
              "html_renders_ok","wpcron_reliable","keyword_data"):
        assert k in s["probe"], k
def test_courses_yaml_shape():
    c = yaml.safe_load((ROOT/"courses/trainingint.yaml").read_text())
    assert c["site"] == "trainingint"
    course = c["courses"][0]
    for k in ("id","course_url","pillar","cluster","secondary_courses"):
        assert k in course
    assert course["cluster"][0]["status"] in ("idea","proposed")
