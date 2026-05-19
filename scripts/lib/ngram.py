import re, html, unicodedata
def _norm(t):
    # Strip HTML tags + decode entities + fold to ascii so the metric compares
    # PROSE not markup: ae-6/ae-8 feed HTML (04-seo.html) vs markdown (03-voice.md),
    # and WordPress emits smart quotes/entities. Plain text is unaffected (no-op).
    t=html.unescape(re.sub(r"<[^>]+>", " ", t))
    t=unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", t.lower())
def shingles(text, n=8):
    w=_norm(text)
    return [tuple(w[i:i+n]) for i in range(len(w)-n+1)] if len(w)>=n else []
def overlap_8gram(a,b,n=8):
    sb={s for s in shingles(b,n)}
    return list(dict.fromkeys(" ".join(s) for s in shingles(a,n) if s in sb))
def voice_survival_ratio(seo_text, voice_text, n=8):
    vs=set(shingles(voice_text,n))           # distinct voice n-grams (denominator)
    if not vs: return 1.0
    se={s for s in shingles(seo_text,n)}
    return sum(1 for s in vs if s in se)/len(vs)
