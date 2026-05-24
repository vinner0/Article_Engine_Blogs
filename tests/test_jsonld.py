import json
from scripts.lib.jsonld import build_jsonld
def _b(**kw):
    base=dict(url="https://t/x/", title="How to X", description="d",
              author="Vinai Prakash", publisher="Intellisoft Training Pte Ltd",
              faqs=[{"q":"Q1?","a":"A1."}],
              breadcrumb=[("Home","https://t/"),("Blog","https://t/blog/"),
                          ("How to X","https://t/x/")])
    base.update(kw); return json.loads(build_jsonld(**base))
def test_three_nodes_and_content():
    g=_b()["@graph"]
    by={n["@type"]:n for n in g}
    assert {"Article","FAQPage","BreadcrumbList"} <= set(by)
    assert by["Article"]["headline"]=="How to X"          # content, not just count
    assert [i["position"] for i in by["BreadcrumbList"]["itemListElement"]]==[1,2,3]
    assert by["FAQPage"]["mainEntity"][0]["name"]=="Q1?"
def test_suppress_skips_node():   # ADVERSARIAL: a stub that ignores suppress fails
    types={n["@type"] for n in _b(suppress={"FAQPage"})["@graph"]}
    assert "FAQPage" not in types and "Article" in types
def test_suppress_article_keeps_others():   # the real seo_plugin_emits_graph case
    types={n["@type"] for n in _b(suppress={"Article"})["@graph"]}
    assert "Article" not in types and "FAQPage" in types
def test_suppress_breadcrumb():
    types={n["@type"] for n in _b(suppress={"BreadcrumbList"})["@graph"]}
    assert "BreadcrumbList" not in types and "Article" in types
def test_faqs_empty_no_faqpage_node():      # guards the `and faqs` short-circuit
    types={n["@type"] for n in _b(faqs=[])["@graph"]}
    assert "FAQPage" not in types and "Article" in types
def test_breadcrumb_empty_no_node():
    types={n["@type"] for n in _b(breadcrumb=[])["@graph"]}
    assert "BreadcrumbList" not in types
def test_all_suppressed_empty_graph():
    assert _b(suppress={"Article","FAQPage","BreadcrumbList"})["@graph"]==[]
def test_multi_faq_positions_and_count():
    g=_b(faqs=[{"q":"Q1?","a":"A1."},{"q":"Q2?","a":"A2."}])["@graph"]
    fp=[n for n in g if n["@type"]=="FAQPage"][0]
    assert [m["name"] for m in fp["mainEntity"]]==["Q1?","Q2?"]
def test_script_breakout_escaped():   # ADVERSARIAL C1: raw json.dumps fails this
    raw=build_jsonld(url="https://t/x/",title="T",description="d",author="A",
        publisher="P",faqs=[{"q":"Q?","a":"x </script><script>alert(1)</script>"}],
        breadcrumb=[("Home","https://t/")])
    assert "</script>" not in raw and "<\\/script>" in raw
    assert json.loads(raw)["@graph"]                 # still valid JSON
def test_author_same_as_emitted_when_provided():   # B5: E-E-A-T author identity
    art=[n for n in _b(author_same_as=[
            "https://www.linkedin.com/in/vinaiprakash",
            "https://www.youtube.com/@excelchamp",
            "https://www.vinaiprakash.com"])["@graph"] if n["@type"]=="Article"][0]
    assert art["author"]["sameAs"]==[
        "https://www.linkedin.com/in/vinaiprakash",
        "https://www.youtube.com/@excelchamp",
        "https://www.vinaiprakash.com"]
def test_author_no_same_as_by_default():           # ADVERSARIAL: stub that always adds fails
    art=[n for n in _b()["@graph"] if n["@type"]=="Article"][0]
    assert "sameAs" not in art["author"]
def test_article_optional_fields():   # I1: image/dates emitted only when provided
    art=[n for n in _b(image_url="https://t/i.jpg",date_published="2026-06-01",
            date_modified="2026-06-02")["@graph"] if n["@type"]=="Article"][0]
    assert art["image"]=="https://t/i.jpg" and art["datePublished"]=="2026-06-01" \
       and art["dateModified"]=="2026-06-02"
    art2=[n for n in _b()["@graph"] if n["@type"]=="Article"][0]
    assert "image" not in art2 and "datePublished" not in art2  # absent by default
