# Link budget rules (per blog post)

| Type | Count | Where | Anchor rule |
|---|---|---|---|
| Internal — softskills.sg blog (related posts) | 3–5 | Body, in context | Descriptive partial-match, varied |
| Internal — softskills.sg course/category | 1–2 | Body + CourseCTA block | Course title; not "click here" |
| External — trainingint.com (WSQ courses) | **2–3** | Body, topically natural | Full or partial course title |
| External — intellisoft.com.sg | 0–1 | Body, only when natural | Course title; skip if forced |
| Authoritative outbound (E-E-A-T) | 1–2 | Body | SSG, MOM, HBR, McKinsey, peer-reviewed |

## Hard rules
- Same URL never repeated within a post
- No naked URLs / "click here" / "learn more" as anchor
- Cross-domain links: `target="_blank" rel="noopener"`
- Cross-business links (trainingint, intellisoft) do **not** carry `rel="sponsored"` (same group, not paid placement)
- One primary CTA above fold + one bottom-of-post; no mid-post pop-ups
- Anchor diversity: no two anchors identical; no >40% of internal links use exact-match keyword as anchor

## Refuse-to-publish triggers
- `> 3` trainingint links
- `> 1` intellisoft link
- `0` internal softskills.sg blog links (orphan post)
- `0` authoritative outbound (E-E-A-T fail)
- Same domain repeated in same paragraph (spam pattern)
