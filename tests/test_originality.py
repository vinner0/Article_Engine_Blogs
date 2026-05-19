from scripts.lib.originality import originality_report
STORIES="A trainee once emailed the whole company by mistake. We laughed, then fixed it."
STATS="24 years training in Singapore. 48,000+ working professionals trained."
def test_passes_story_and_stat():
    art=("Real case: A trainee once emailed the whole company by mistake. We "
         "laughed, then fixed it. We have 24 years training in Singapore behind this.")
    r=originality_report(art, STORIES, STATS, ["generic competitor copy about emails"])
    assert r["passes"] and r["count"]>=2
def test_fails_zero_elements():
    art="Generic advice about writing emails that competitors also say."
    r=originality_report(art, STORIES, STATS, [art])
    assert not r["passes"] and r["count"]==0
def test_no_op_pass_stub_fails():     # ADVERSARIAL: {"passes":True} stub fails this
    art="nothing original here at all just filler words repeated repeated"
    r=originality_report(art, STORIES, STATS, [art])
    assert not r["passes"]
