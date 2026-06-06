from scripts.lib.ngram import shingles, overlap_8gram, voice_survival_ratio
def test_shingles_count():
    assert len(shingles("a b c d e f g h i", 8)) == 2
def test_overlap_detects_shared_phrase():
    a="you should always proofread your email before you hit send today"
    b="experts say you should always proofread your email before you hit send"
    assert any("proofread your email before you hit send" in h for h in overlap_8gram(a,b))
def test_overlap_no_op_implementation_fails():     # ADVERSARIAL: return [] fails this
    t="alpha beta gamma delta epsilon zeta eta theta iota kappa"
    assert overlap_8gram(t,t)
def test_voice_survival():
    v="one two three four five six seven eight nine ten eleven twelve"
    assert voice_survival_ratio(v,v) == 1.0
    assert voice_survival_ratio("completely different words none shared at all here now then",v) < 0.85
def test_voice_survival_html_vs_markdown_not_false_blocked():  # ADVERSARIAL: real call
    # ae-6/ae-8 call voice_survival_ratio(04-seo.html, 03-voice.md): HTML (tags,
    # entities, smart quotes, embedded JSON-LD) vs markdown of the SAME prose must
    # NOT trip the <0.85 gate. A _norm that does not strip markup scores ~0.4 here.
    prose=("Writing a professional email is not hard once you accept that "
           "clarity beats cleverness every single time you sit down to type one")
    md="## Heading\n\n"+prose+"\n\n- a bullet point that is here too\n"
    h=("<h2>Heading</h2><p>"+prose+"</p><ul><li>a bullet point that is here too"
       "</li></ul><script type=\"application/ld+json\">{\"@type\":\"Article\"}</script>")
    assert voice_survival_ratio(h, md) >= 0.85
def test_overlap_dedupes_repeated_match():        # ADVERSARIAL: list (dup) fails this
    rep="copied sentence that appears verbatim in the competitor body text here now"
    art=rep+". filler words in between here. "+rep+"."
    o=overlap_8gram(art, rep)
    assert o and len(o)==len(set(o))

# --- prose-only gate (2026-06: exclude non-prose metadata + code) ---
def test_overlap_ignores_yaml_frontmatter():
    # The post title (frontmatter) MUST carry the primary keyword, which also appears
    # in a competitor's title. That metadata match is not plagiarised prose.
    art=('---\ntitle: How to Make a Gantt Chart in Excel a Step by Step Guide\n'
         'slug: x\n---\n<p>Wholly original body that shares no long phrase with them.</p>')
    src='how to make a gantt chart in excel a step by step guide for beginners'
    assert overlap_8gram(art, src) == []
def test_overlap_ignores_comment_wrapped_frontmatter():
    art=('<!--\n---\ntitle: How to Make a Gantt Chart in Excel a Step by Step Guide\n'
         '---\n-->\n<p>Wholly original body that shares no long phrase with them.</p>')
    src='how to make a gantt chart in excel a step by step guide for beginners'
    assert overlap_8gram(art, src) == []
def test_overlap_ignores_code_blocks():
    formula='IF AND B2 greater 90 C2 greater 5 then Bonus else Review else None always'
    art='<p>Use the nested formula below.</p><pre>'+formula+'</pre>'
    src='some preamble '+formula+' some trailing words'
    assert overlap_8gram(art, src) == []   # only the code is shared, not prose
def test_overlap_ignores_markdown_fenced_code():
    formula='SUMIFS range one criteria one range two criteria two and so on forever now'
    art='Intro prose here.\n\n```\n'+formula+'\n```\n\nmore unique prose.'
    src='blah '+formula+' blah'
    assert overlap_8gram(art, src) == []
def test_overlap_still_flags_real_body_plagiarism_despite_frontmatter():
    art=('---\ntitle: Anything\n---\n<p>experts agree you should always proofread '
         'your email before you hit the send button</p>')
    src='you should always proofread your email before you hit the send button now'
    assert overlap_8gram(art, src)   # true positive must survive the prose-only change
def test_voice_survival_ignores_frontmatter_title_change():
    body=('the quick brown fox jumps over the lazy dog again and again and again here now')
    voice='---\ntitle: alpha beta gamma delta epsilon zeta eta theta iota kappa\n---\n'+body
    seo='---\ntitle: one two three four five six seven eight nine ten eleven\n---\n<p>'+body+'</p>'
    assert voice_survival_ratio(seo, voice) >= 0.85  # only allowed title edit changed
