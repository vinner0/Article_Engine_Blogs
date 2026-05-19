import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
V=["voice.md","humor.md","opinions.md","stats.md","stories.md","do-not-write.md"]
S=["checklist.md","link-budget.md","schema-templates.md","audit-budgets.yaml","pillar-map.yaml"]
def test_voice_present():
    for f in V:
        p=ROOT/"voice"/f; assert p.exists() and p.stat().st_size>100, f
    assert "24 years" in (ROOT/"voice/stats.md").read_text(encoding="utf-8")
def test_seo_present():
    for f in S:
        p=ROOT/"seo"/f; assert p.exists() and p.stat().st_size>100, f
    assert "Refuse-to-publish" in (ROOT/"seo/link-budget.md").read_text(encoding="utf-8")
