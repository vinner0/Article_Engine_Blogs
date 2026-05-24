# On-page SEO checklist (80+ items)

Run by `/blog-seo-pass`. Output: `_audit/seo-checklist.md` per post with PASS/FAIL each.

## Title & meta (8)
1. Primary keyword present in `<title>`
2. Title core ≤ 60 characters (the ` ({year}) | {brand_suffix}` from config may extend it — Google renders by pixel width)
3. Primary keyword near front of title (first 30 chars)
3b. Title carries year + geo/brand suffix per `config/sites.yaml` seo_title (not geo-blind)
4. Meta description 140–160 characters
5. Meta description includes a CTA verb (read, learn, get, discover, see)
6. Primary keyword in meta description
7. No duplicate `<title>` sitewide
8. OpenGraph + Twitter card meta present

## Headings (6)
9. Exactly one `<h1>`
10. `<h1>` contains primary keyword (or close variant)
11. 4–8 `<h2>` headings
12. `<h2>` headings contain semantic variations from the keyword cluster
13. `<h3>` are logically nested under `<h2>`
14. No `<h4>` or deeper unless format demands

## Body content (15)
15. Primary keyword in first 100 words
16. Keyword density 0.5–1.5%
17. All secondary cluster keywords appear at least once
18. 4–8 FAQ block at end
19. TL;DR / answer-first paragraph in first 150 words (snippet bait)
20. Tables, ordered lists, or numbered steps present where format supports
21. ≥1 original analogy (Vinai voice signature)
22. ≥1 stat from `voice/stats.md` (verbatim)
23. ≥1 story from `voice/stories.md`
24. Internal-link anchor diversity: no two anchors identical
25. All images have descriptive alt text
26. Hero image alt contains primary keyword (other images don't have to)
27. Reading time computed and visible
28. Last-updated date visible if `updatedAt` set
29. Author byline visible

## Images (6)
30. WebP via `astro:assets`
31. Width and height attributes set (no CLS)
32. Lazy-loaded below fold
33. Slug-style filenames (no `DSC_1234.jpg`)
34. Alt text 8–80 characters
35. No alt-text spam (decorative images have empty alt)

## Internal/external links (per Section 3 of spec)
36. 3–5 internal softskills.sg blog links
37. 1–2 internal softskills.sg course/category links
38. 2–3 trainingint.com deep links
39. 0–1 intellisoft.com.sg deep link
40. 1–2 authoritative outbound (SSG, MOM, HBR, McKinsey, peer-reviewed)
41. No same URL repeated in post
42. Anchor diversity: no >40% of internal links use exact-match keyword as anchor
43. No naked URLs
44. No "click here" / "learn more" anchors
45. Cross-domain links open in new tab with `rel="noopener"`
46. Cross-business links (trainingint, intellisoft) do NOT carry `rel="sponsored"`
47. ONE primary CTA above fold + ONE bottom of post
48. No mid-post pop-ups

## Technical / snippet bait (5)
49. Clean kebab-case URL slug, ≤60 chars, no stop words
50. Canonical tag present and matches the URL
51. `hreflang="en-SG"` present — **MANUAL/WP (not engine-checkable).** Yoast-free does not emit hreflang and the engine never injects `<head>` link tags; verified absent on all live pages 2026-05-24. Tracked in `docs/seo-ops-checklist.md`. `scripts/audit_live.py` reports its presence as INFO, never FAIL.
52. JSON-LD validates via Google Rich Results Test
53. Table-of-contents block for posts ≥3 H2s — **auto-injected at publish** (scripts/wp_publish.py inject_toc); do not hand-author

## Schema (3)
54. Article JSON-LD present and valid
55. FAQPage JSON-LD present and valid (matches frontmatter `faqs`)
56. BreadcrumbList JSON-LD present

## Author / E-E-A-T (4)
57. AuthorBio block present
58. Author byline links to `/about-us` or vinaiprakash.com
59. At least one stat from `voice/stats.md` referenced
60. At least one credential mentioned (ACTA / 24 years / 48,000+)

## Originality (4)
61. ≥2 of: story, original analogy, Vinai stat, original framework
62. No 8-word phrase shared with top-3 SERP competitors
63. Voice-pass artifact (`_draft/03-voice.md`) exists in repo
64. Human edit gate evidence (commit by Vinai between voice-pass and seo-pass)

## Performance hooks (these get measured by Lighthouse, not this checklist)
65. Hero image preloaded with `<link rel=preload as=image>`
66. Hero image ≤ 80KB after compression
67. Below-fold images lazy-loaded
68. Self-hosted fonts (no Google Fonts CDN)

## Cadence (1)
69. ≤2 posts published in last 7 days (cadence guard)

## Pillar discipline (3)
70. Frontmatter `pillar` is one of P1–P5
71. Frontmatter `cluster` is registered in `seo/pillar-map.yaml`
72. `primaryKeyword` is unique across `pillar-map.yaml` (no self-cannibalisation)

## Course CTA (3)
73. Frontmatter `courseLinks.primary` resolves (200)
74. Each `courseLinks.trainingint` URL resolves (200)
75. CourseCTA block uses real course title from `voice/stats.md` flagship list

## Misc (5)
76. No `lorem ipsum` placeholder text
77. No "TBD" / "TODO" / `[INSERT X HERE]`
78. All links resolve (200)
79. No broken images
80. Frontmatter validates against Zod schema

## SEO audit additions — 2026-05-24 (8)
81. **No residual `ae:` placeholder** — no `ae:sibling:` / `ae:img:` token survives to the body (publish fail-closed gate enforces this; a survivor means status_map/images_dir wasn't passed)
82. Author JSON-LD carries `sameAs` (LinkedIn/YouTube/site) — via `build_jsonld(author_same_as=...)`, OR set in the SEO plugin's Person settings when it emits the @graph (trainingint: Yoast Person)
83. Jumplink TOC present + every `<h2>` has a slug `id` anchor (auto-injected at publish for ≥3 H2s)
84. Related-Articles block present near the bottom (3–4 hand-picked siblings via `scripts.lib.blocks.render_related`)
85. Styled course card at peak intent (`scripts.lib.blocks.render_course_card`) — funding badge + Register button; no hardcoded price/intake
86. 8–12 total internal links (inline siblings + course links + related block)
87. Image alt is specific (subject/action + keyword context), not generic stock; filenames are slug-style + keyword-bearing
88. HowTo / Course schema NOT emitted on blog posts (deliberate — see ae-6 spec)
