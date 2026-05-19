import pathlib
from scripts.lib.originality import originality_report
ROOT=pathlib.Path(__file__).resolve().parents[1]
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
def test_real_inputs_html_article():  # ADVERSARIAL: real call site passes 04-seo.html
    stories=(ROOT/"voice/stories.md").read_text(encoding="utf-8")
    stats=(ROOT/"voice/stats.md").read_text(encoding="utf-8")
    html=("<article><h2>Steps</h2><ol>"
          "<li>Define the one outcome the email must achieve</li>"
          "<li>Write the ask in the first two sentences</li>"
          "<li>Cut every sentence that does not serve that ask</li>"
          "</ol><p>Think of a good email like a one-page memo.</p></article>")
    r=originality_report(html, stories, stats,
                         ["totally unrelated competitor prose about kittens here"])
    assert r["checks"]["original_framework"] is True   # HTML <ol> must count (pre-fix: False)
    assert r["checks"]["original_analogy"] is True      # "like a one-page memo"
def test_course_name_alone_does_not_pass(): # ADVERSARIAL: stat needs a digit; "like you" != simile
    stories=(ROOT/"voice/stories.md").read_text(encoding="utf-8")
    stats=(ROOT/"voice/stats.md").read_text(encoding="utf-8")
    art=("Our course Communicate with Confidence helps professionals like you "
         "improve at work and grow in their roles over time consistently here today.")
    r=originality_report(art, stories, stats,
                         ["unrelated competitor text about an entirely different subject"])
    assert r["passes"] is False   # pre-fix: stat(course name)+analogy("like you") => True
