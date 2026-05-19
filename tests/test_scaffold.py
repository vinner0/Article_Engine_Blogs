import importlib
def test_libs_importable():
    for m in ("scripts.lib.ngram","scripts.lib.originality",
              "scripts.lib.link_budget","scripts.lib.jsonld"):
        importlib.import_module(m)
