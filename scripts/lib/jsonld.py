import json, re
def build_jsonld(url,title,description,author,publisher,faqs,breadcrumb,
                 suppress=None,image_url=None,date_published=None,date_modified=None,
                 author_same_as=None):
    suppress=suppress or set(); g=[]
    if "Article" not in suppress:
        person={"@type":"Person","name":author}
        if author_same_as:                       # E-E-A-T: link the author identity to
            person["sameAs"]=list(author_same_as)  # LinkedIn / YouTube / personal site
        art={"@type":"Article","headline":title,"description":description,
             "mainEntityOfPage":url,
             "author":person,
             "publisher":{"@type":"Organization","name":publisher}}
        if image_url: art["image"]=image_url
        if date_published: art["datePublished"]=date_published
        if date_modified: art["dateModified"]=date_modified
        g.append(art)
    if "FAQPage" not in suppress and faqs:
        g.append({"@type":"FAQPage","mainEntity":[
            {"@type":"Question","name":f["q"],
             "acceptedAnswer":{"@type":"Answer","text":f["a"]}} for f in faqs]})
    if "BreadcrumbList" not in suppress and breadcrumb:
        g.append({"@type":"BreadcrumbList","itemListElement":[
            {"@type":"ListItem","position":i+1,"name":n,"item":u}
            for i,(n,u) in enumerate(breadcrumb)]})
    # `</` -> `<\/` so an answer containing </script> cannot break out of the
    # in-HTML <script type="application/ld+json"> block ae-6 embeds this in.
    # `\/` is a valid JSON escape for `/`, so json.loads() is unaffected.
    return json.dumps({"@context":"https://schema.org","@graph":g}).replace("</","<\\/")

def repair_jsonld_script_close(html):
    """Repair ld+json <script> blocks whose CLOSING tag was escaped to <\\/script>
    instead of a literal </script> (a generation bug that leaves the block unclosed
    in the browser). For each application/ld+json opening, find where its JSON value
    ends via json.raw_decode — which safely treats any <\\/script> INSIDE a string
    value as data, not the close — then, if the next non-space token is an escaped
    close, rewrite it to a literal </script>. Returns (repaired_html, n_fixed).
    Idempotent: a block already closed by a literal </script> is left untouched.
    Processes right-to-left so earlier spans' indices stay valid after splicing."""
    dec = json.JSONDecoder()
    n = 0
    spans = list(re.finditer(r'<script[^>]*application/ld\+json[^>]*>', html, re.I))
    for m in reversed(spans):
        k = m.end()
        while k < len(html) and html[k] in ' \t\r\n':
            k += 1
        try:
            _, end = dec.raw_decode(html, k)
        except ValueError:
            continue                      # not clean JSON at the opening; leave for the gate
        j = end
        while j < len(html) and html[j] in ' \t\r\n':
            j += 1
        if html.startswith('<\\/script>', j):
            html = html[:j] + '</script>' + html[j + len('<\\/script>'):]
            n += 1
    return html, n
