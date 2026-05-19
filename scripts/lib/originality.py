import re
from scripts.lib.ngram import overlap_8gram
# YAML key / markdown header / blockquote — not story prose (skip in _has_story)
_KEYISH=re.compile(r"^\s*(#|>|[\w-]+\s*:(\s|$))")
def _story_lines(stories):
    for raw in stories.splitlines():
        ln=raw.strip(" -*")
        if ln and not _KEYISH.match(raw): yield ln
def _has_story(a, stories):
    al=a.lower()
    for ln in _story_lines(stories):
        if len(ln)>30 and ln[:30].lower() in al: return True
    return False
def _has_stat(a, stats):
    al=a.lower()
    for ln in (l.strip(" -*") for l in stats.splitlines()):
        frag=ln.split(".")[0].strip()
        # a real stat is numeric — exclude course names / bio / headers
        if len(frag)>6 and any(ch.isdigit() for ch in frag) and frag.lower() in al:
            return True
    return False
def _has_analogy(a, serp):
    for s in a.replace("\n"," ").split("."):
        sl=s.lower()
        if (re.search(r"\blike (a|an|the) ", sl)
                or any(c in sl for c in ("is like","think of it as","imagine ","as if "))):
            if not any(overlap_8gram(s,b) for b in serp): return True
    return False
def _framework_block(a):
    # article at the real call site is 04-seo.html — count HTML <li> AND markdown
    md=[l for l in a.splitlines() if re.match(r"\s*(\d+\.|\-|\*)\s+\S", l)]
    li=re.findall(r"<li\b[^>]*>(.*?)</li>", a, re.DOTALL|re.IGNORECASE)
    return ("\n".join(md)+"\n"+"\n".join(li)).strip()
def _has_framework(a, serp):
    block=_framework_block(a)
    return bool(block) and not any(overlap_8gram(block,b) for b in serp)
def originality_report(article, stories_md, stats_md, serp_bodies):
    c={"story":_has_story(article,stories_md),"stat":_has_stat(article,stats_md),
       "original_analogy":_has_analogy(article,serp_bodies),
       "original_framework":_has_framework(article,serp_bodies)}
    n=sum(c.values())
    return {"passes": n>=2, "count": n, "checks": c}
