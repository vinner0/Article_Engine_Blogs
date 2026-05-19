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
