from scripts.lib.link_budget import validate_links
B={"internal_sibling_min":2,"internal_sibling_max":3,"primary_course_distinct":1,
   "primary_course_occurrences_max":3,"secondary_course_max":3,
   "authoritative_outbound_min":1,"authoritative_outbound_max":2}
def test_clean_passes():
    inv={"internal_sibling":["/blog/a","/blog/b"],
         "primary_course":["u","u","u"],"secondary_course":["y"],
         "authoritative_outbound":["https://www.skillsfuture.gov.sg/"],
         "anchors":["a1","a2","a3","a4","a5"],"same_paragraph_domains":[]}
    assert validate_links(inv,B)==[]
def test_too_many_primary_occurrences():   # ADVERSARIAL: return [] stub fails
    inv={"internal_sibling":["/a","/b"],"primary_course":["u"]*5,
         "secondary_course":[],"authoritative_outbound":["https://mom.gov.sg"],
         "anchors":["a","b","c","d","e","f","g"],"same_paragraph_domains":[]}
    assert any("primary_course_occurrences" in x for x in validate_links(inv,B))
def test_orphan_and_eeat():
    inv={"internal_sibling":[],"primary_course":["u"],"secondary_course":[],
         "authoritative_outbound":[],"anchors":["x"],"same_paragraph_domains":[]}
    v=validate_links(inv,B)
    assert any("internal_sibling_min" in x for x in v)
    assert any("authoritative_outbound_min" in x for x in v)
def test_dup_anchor_and_spam():
    inv={"internal_sibling":["/a","/b"],"primary_course":["u"],"secondary_course":[],
         "authoritative_outbound":["https://hbr.org"],"anchors":["same","same"],
         "same_paragraph_domains":["trainingint.com"]}
    v=validate_links(inv,B)
    assert any("identical_anchor" in x for x in v)
    assert any("same_paragraph" in x for x in v)
