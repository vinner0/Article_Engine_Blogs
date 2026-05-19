import re
def _norm(t): return re.findall(r"[a-z0-9]+", t.lower())
def shingles(text, n=8):
    w=_norm(text)
    return [tuple(w[i:i+n]) for i in range(len(w)-n+1)] if len(w)>=n else []
def overlap_8gram(a,b,n=8):
    sb={s for s in shingles(b,n)}
    return [" ".join(s) for s in shingles(a,n) if s in sb]
def voice_survival_ratio(seo_text, voice_text, n=8):
    vs=shingles(voice_text,n)
    if not vs: return 1.0
    se={s for s in shingles(seo_text,n)}
    return sum(1 for s in vs if s in se)/len(vs)
