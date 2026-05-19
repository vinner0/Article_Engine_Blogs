import re
from scripts.lib.ngram import overlap_8gram
def _has_story(a, stories):
    for ln in (l.strip(" -*") for l in stories.splitlines()):
        if len(ln)>30 and ln[:30].lower() in a.lower(): return True
    return False
def _has_stat(a, stats):
    for ln in (l.strip(" -*") for l in stats.splitlines()):
        frag=ln.split(".")[0].strip()
        if len(frag)>6 and frag.lower() in a.lower(): return True
    return False
def _has_analogy(a, serp):
    for s in a.replace("\n"," ").split("."):
        if any(c in s.lower() for c in ("like ","is like","think of it as","imagine ","as if ")):
            if not any(overlap_8gram(s,b) for b in serp): return True
    return False
def _has_framework(a, serp):
    if re.search(r"(?m)^\s*(\d+\.|\-|\*)\s+\S", a):
        block="\n".join(l for l in a.splitlines() if re.match(r"\s*(\d+\.|\-|\*)\s+\S", l))
        return bool(block) and not any(overlap_8gram(block,b) for b in serp)
    return False
def originality_report(article, stories_md, stats_md, serp_bodies):
    c={"story":_has_story(article,stories_md),"stat":_has_stat(article,stats_md),
       "original_analogy":_has_analogy(article,serp_bodies),
       "original_framework":_has_framework(article,serp_bodies)}
    n=sum(c.values())
    return {"passes": n>=2, "count": n, "checks": c}
