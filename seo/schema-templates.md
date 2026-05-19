# Schema.org templates (reference)

The implementations in `src/lib/schema/*.ts` are the source of truth. This file is the human-readable companion.

## Sitewide (in `BaseLayout`)
- **Organization** — once per page, `sameAs` includes trainingint.com, intellisoft.com.sg, vinaiprakash.com (domain-cluster trust signal)

## Per blog post (in `BlogLayout`)
- **Article** — author → Person (Vinai bio); publisher → Organization (softskills.sg)
- **FAQPage** — populated from frontmatter `faqs` (4–8 Q&A pairs); wins PAA SERP feature
- **BreadcrumbList** — Home → Blog → Pillar → Post

## Deliberately NOT emitted on blog posts
- **Course** schema (belongs on actual course pages, not blog posts — wrong-schema-on-wrong-page is a quality hit)
- **HowTo** schema (Google deprecated rich-result eligibility for non-DIY content)

## Validation
- After publish: paste post URL into [Google Rich Results Test](https://search.google.com/test/rich-results) — must validate clean
- After publish: paste post URL into [Schema.org Validator](https://validator.schema.org/) — must validate clean
