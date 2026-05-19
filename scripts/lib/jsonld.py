import json
def build_jsonld(url,title,description,author,publisher,faqs,breadcrumb,suppress=None):
    suppress=suppress or set(); g=[]
    if "Article" not in suppress:
        g.append({"@type":"Article","headline":title,"description":description,
                  "mainEntityOfPage":url,
                  "author":{"@type":"Person","name":author},
                  "publisher":{"@type":"Organization","name":publisher}})
    if "FAQPage" not in suppress and faqs:
        g.append({"@type":"FAQPage","mainEntity":[
            {"@type":"Question","name":f["q"],
             "acceptedAnswer":{"@type":"Answer","text":f["a"]}} for f in faqs]})
    if "BreadcrumbList" not in suppress and breadcrumb:
        g.append({"@type":"BreadcrumbList","itemListElement":[
            {"@type":"ListItem","position":i+1,"name":n,"item":u}
            for i,(n,u) in enumerate(breadcrumb)]})
    return json.dumps({"@context":"https://schema.org","@graph":g})
