import json
def build_jsonld(url,title,description,author,publisher,faqs,breadcrumb,
                 suppress=None,image_url=None,date_published=None,date_modified=None):
    suppress=suppress or set(); g=[]
    if "Article" not in suppress:
        art={"@type":"Article","headline":title,"description":description,
             "mainEntityOfPage":url,
             "author":{"@type":"Person","name":author},
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
