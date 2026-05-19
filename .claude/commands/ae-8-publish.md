---
description: Stage 8 — push a reviewed slug to WordPress as a future-dated scheduled post. Strict gates. Idempotent (no duplicate on rerun).
argument-hint: <slug> [--override]
---

# /ae-8-publish

Stage 8 for `$ARGUMENTS` on trainingint.com.
**Spec:** docs/superpowers/specs/2026-05-19-article-engine-design.md §8

## PRE-FLIGHT GATES (refuse if any fail; only --override bypasses cadence)
1. **Probe gate (HARD):** from config/sites.yaml sites.trainingint.probe, REFUSE unless
   ALL of: rest_ok==true, uid_roundtrip_ok==true, seo_meta_rest_writable is not null,
   default_category_id is not null, default_author_id is not null,
   seo_plugin_emits_graph is not null,
   html_renders_ok==true, wpcron_reliable==true, keyword_data is not null.
   (A null here means P0/Task 15 Step 1 is incomplete — do not publish blind.)
2. **Cadence guard:** count status/trainingint.yaml entries with scheduled_date in the
   last 7 days; if > cadence.per_week (5), REFUSE unless --override.
3. **Voice-damage:** scripts.lib.ngram.voice_survival_ratio(04-seo.html, 03-voice.md) ≥ 0.85.
4. **Originality:** scripts.lib.originality.originality_report(...).passes is True.
5. **Anti-plagiarism:** scripts.lib.ngram.overlap_8gram(article, each _research/serp-bodies/*.txt)
   is empty; else REFUSE naming the phrase.
6. **Link budget:** scripts.lib.link_budget.validate_links(inv, budget) == [].
7. **Course registration:** $ARGUMENTS exists in courses/trainingint.yaml with matching
   primary_keyword and a course_url; else REFUSE.

## Publish (single idempotent call)
**Derive the call inputs from `04-seo.html`'s frontmatter (do not invent them):**
- `title` = frontmatter `title`; `description` = frontmatter `description`; `html` = the `04-seo.html` body (post-frontmatter).
- `featured_path` = `content/trainingint/<slug>/images/<heroImage>` where `heroImage` is the frontmatter field.
- `seo_meta` = a dict keyed by the ACTIVE plugin from `probe.seo_plugin`:
  `yoast` → `{"_yoast_wpseo_title": title, "_yoast_wpseo_metadesc": description}`;
  `rankmath` → `{"rank_math_title": title, "rank_math_description": description}`;
  `none` → `{}` (no plugin meta).
- `tags` = keyword-derived tag names from `_research/cluster.md` (or omit / `None`).
- `scheduled_iso` = next free weekday 09:00 Singapore (UTC+8) slot, reading existing
  `scheduled_date` entries in `status/trainingint.yaml` (cadence 5/wk Mon–Fri).
  **If `status/trainingint.yaml` does not exist yet, treat it as empty — the first
  slot is the next weekday 09:00 SGT.**

Run python that loads config + credentials/.env, builds WPClient, then calls
scripts.wp_publish.publish_article(wp, content_uid('trainingint',slug), slug,
title, html, seo_meta, scheduled_iso, probe.default_category_id, probe.default_author_id,
featured_path=<hero image>, status_map=<status/trainingint.yaml dict, or None if absent>,
seo_meta_rest_writable=probe.seo_meta_rest_writable,
tags=<derived tags or omit>,
images_dir=content/trainingint/<slug>/images/ ). Idempotent: rerun UPDATES, never
duplicates (helper /ae/v1/find + adversarial-tested in scripts/wp_publish.py).
Inline `ae:img:<file>` placeholders + the hero are uploaded to WP media and rewritten
to live URLs (spec §8.2); `tags` set alongside category/author (spec §8.3).
If `seo_meta_rest_writable` is false, publish_article routes `seo_meta` through the
helper `/ae/v1/meta` route automatically (spec §8.4).

## After publish
Update status/trainingint.yaml: slug → {status: scheduled, scheduled_date, wp_post_id}.
Surface: post id, scheduled date, wp-admin edit URL
(https://www.trainingint.com/wp-admin/post.php?post=<id>&action=edit), and any
unresolved sibling links returned (they were dropped to plain text — they re-link
naturally when the sibling publishes and that article is regenerated/edited).

## Refuse if any gate fails — say which gate and the exact failure.
