_REQ=("internal_sibling","primary_course","secondary_course",
      "authoritative_outbound","anchors","same_paragraph_domains")
def validate_links(inv, budget):
    missing=[k for k in _REQ if k not in inv]
    if missing:                       # ae-6 builds inv in prose — fail diagnostic, not KeyError
        return [f"inventory_incomplete: missing keys {missing}"]
    v=[]
    sib=inv["internal_sibling"]
    if len(sib)<budget["internal_sibling_min"]:
        v.append(f"internal_sibling_min: {len(sib)} < {budget['internal_sibling_min']}")
    if len(sib)>budget["internal_sibling_max"]:
        v.append(f"internal_sibling_max: {len(sib)} > {budget['internal_sibling_max']}")
    pc=inv["primary_course"]
    if len(set(pc))>budget["primary_course_distinct"]:
        v.append(f"primary_course_distinct: {len(set(pc))} > {budget['primary_course_distinct']}")
    if len(pc)>budget["primary_course_occurrences_max"]:
        v.append(f"primary_course_occurrences: {len(pc)} > {budget['primary_course_occurrences_max']}")
    if len(inv["secondary_course"])>budget["secondary_course_max"]:
        v.append(f"secondary_course_max: {len(inv['secondary_course'])} > {budget['secondary_course_max']}")
    ao=inv["authoritative_outbound"]
    if len(ao)<budget["authoritative_outbound_min"]:
        v.append(f"authoritative_outbound_min: {len(ao)} < {budget['authoritative_outbound_min']}")
    if len(ao)>budget["authoritative_outbound_max"]:
        v.append(f"authoritative_outbound_max: {len(ao)} > {budget['authoritative_outbound_max']}")
    anchors=[a.strip().lower() for a in inv["anchors"]]
    if len(anchors)!=len(set(anchors)):
        v.append("identical_anchor: two or more anchors identical")
    if any(a in {"click here","learn more","read more","here"} for a in anchors):
        v.append("banned_anchor: generic anchor present")
    if any(a.startswith(("http://","https://","www.")) for a in anchors):
        v.append("banned_anchor: naked URL used as anchor")  # link-budget.md L13
    if inv["same_paragraph_domains"]:
        v.append(f"same_paragraph: domain repeated in one paragraph ({inv['same_paragraph_domains']})")
    return v
