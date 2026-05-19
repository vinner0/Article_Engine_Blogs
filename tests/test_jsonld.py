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
