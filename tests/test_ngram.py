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
