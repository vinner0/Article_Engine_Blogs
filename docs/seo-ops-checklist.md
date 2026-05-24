# SEO ops checklist — manual items (not engine code)

From the 2026-05-24 audit of `how-to-use-vlookup-and-xlookup-in-excel`. These live in
WordPress / Yoast / GSC / Search Console / your popup tool — the article engine cannot do
them. Ordered by impact. The engine-side fixes (token gate, schema sameAs hook, TOC,
related block, course card, title template, status sync) are already done in code.

## High impact
- [ ] **Yoast → Person `sameAs`.** Because Yoast emits the page @graph (Article/Breadcrumb/Person),
      the live home for author E-E-A-T is Yoast's Person/Author profile, not the article HTML.
      Set Vinai's: `https://www.vinaiprakash.com`, `https://www.youtube.com/@excelchamp`, and your
      **exact LinkedIn URL** (then also drop that LinkedIn URL into `config/sites.yaml`
      sites.trainingint.author.same_as for portability).
- [ ] **hreflang `en-SG`.** Absent on all live pages (checklist #51 reclassified — the engine cannot
      emit `<head>` link tags and Yoast-free has no hreflang). If you want it, add via a hreflang
      plugin or Yoast Premium; for a single-locale SG site it is low-value. `scripts/audit_live.py`
      reports presence as INFO only.
- [ ] **Cross-domain consolidation.** Nav "Course List" points to intellisoft.com.sg from
      trainingint.com — link equity is split across two domains targeting the same SG audience.
      Pick one primary domain and 301 the other (or stop cross-linking the nav).
- [ ] **`.html` → clean URLs + site-wide 301s.** `/...-in-excel.html` is legacy/verbose. The
      engine already sends clean slugs; the `.html` comes from WP permalink settings. Changing it
      affects EVERY page and needs a full 301 map — high risk. Recommend: stage carefully or defer,
      don't flip casually. If you do it, 301 each old `.html` → new clean URL.

## Medium impact
- [ ] **GSC.** Submit the vlookup URL via URL Inspection after re-publish; then track impressions for
      `vlookup vs xlookup`, `xlookup singapore`, `vlookup not working`, `fix #N/A error`.
- [ ] **WP Rocket / LCP.** Eager-load the hero image (it's the LCP element); lazy-load only
      below-the-fold images. The live page currently lazy-loads the hero (SVG placeholder) — fix that.
- [ ] **Canonical sanity.** Confirm Yoast self-canonical is set and no `?`-param or AMP variants
      compete with it.

## Content / conversion (later passes)
- [ ] **YouTube demo.** Record a 5-min VLOOKUP/XLOOKUP demo on excelchamp, embed it in the article.
      Once embedded, add VideoObject schema (small future engine task — not done yet).
- [ ] **Lead magnet.** "VLOOKUP vs XLOOKUP cheat sheet PDF" → email capture; clone your existing
      "Save Money on Website Design" popup pattern. (Deferred per scope decision.)
- [ ] **Sticky / exit-intent CTA** for the Excel course on long articles + WSQ/SkillsFuture funding
      badge in a sticky footer/sidebar. (Deferred per scope decision.)
- [ ] **Reverse internal links / orphan fix.** Link the article FROM the Excel category hub, the
      Excel course page, and older lookup-related posts (reverse linking is the commonly-missed half).

## Notes
- Price / next-intake are intentionally NOT in the engine's course card — they go stale. The card's
  Register button links to the live course page where those are authoritative.
- HowTo + Course schema are deliberately omitted on blog posts (Google deprecated HowTo rich
  results; Course-on-a-blog-post is a wrong-page signal). Decision logged 2026-05-24.
