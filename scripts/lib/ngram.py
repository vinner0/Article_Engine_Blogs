import re, html, unicodedata
def _strip_nonprose(t):
    # Drop non-prose so the metric compares ARTICLE PROSE only (see _norm docstring):
    #  - a leading YAML frontmatter block (plain or HTML-comment-wrapped): its title/
    #    description carry the primary keyword by design, so they 8-gram-match any
    #    competitor whose title equals that keyword — a metadata match, not plagiarism.
    #  - code (fenced markdown + <pre>/<code>): a correct formula/snippet has exactly
    #    one syntax, so byte-identical code across sources is not copied prose.
    t=re.sub(r"^﻿?\s*(?:<!--\s*\r?\n)?---\r?\n.*?\r?\n---[ \t]*(?:\r?\n[ \t]*-->)?",
             " ", t, count=1, flags=re.DOTALL)
    t=re.sub(r"```.*?```", " ", t, flags=re.DOTALL)
    t=re.sub(r"<(pre|code)\b[^>]*>.*?</\1>", " ", t, flags=re.DOTALL|re.IGNORECASE)
    return t
def _norm(t):
    # Strip HTML tags + decode entities + fold to ascii so the metric compares
    # PROSE not markup: ae-6/ae-8 feed HTML (04-seo.html) vs markdown (03-voice.md),
    # and WordPress emits smart quotes/entities. Plain text is unaffected (no-op).
    t=_strip_nonprose(t)
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
