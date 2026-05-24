from scripts.audit_live import audit_html

# Production-shaped page fragment: a theme title <h1> + a leaked body <h1> (the live
# Outlook shape), one valid ld+json, one broken ld+json, a canonical, a meta desc,
# and a 1x1 display:none tracking pixel (the only legit alt-less image).
GOOD_LD = '{"@context":"https://schema.org","@graph":[{"@type":"Article"}]}'
BAD_LD = '{"@type":"FAQPage"}<\\/script></p><div>junk'  # JSON + appended markup

def _page(h1s=1, good_ld=True, bad_ld=False, canonical="https://x.test/p",
          meta="x"*150, pixel=True):
    parts = ['<head>']
    if canonical:
        parts.append(f'<link rel="canonical" href="{canonical}"/>')
    if meta is not None:
        parts.append(f'<meta name="description" content="{meta}"/>')
    parts.append('</head><body>')
    for i in range(h1s):
        parts.append(f'<h1>Title {i}</h1>')
    if good_ld:
        parts.append(f'<script type="application/ld+json">{GOOD_LD}</script>')
    if bad_ld:
        parts.append(f'<script type="application/ld+json">{BAD_LD}</script>')
    if pixel:
        parts.append('<img height="1" width="1" style="display:none" '
                     'src="https://www.facebook.com/tr?id=1"/>')
    parts.append('<img src="/hero.webp" alt="real hero"/></body>')
    return "".join(parts)

def _result(checks, name):
    return next(c for c in checks if c["check"] == name)

def test_single_h1_passes():
    assert _result(audit_html(_page(h1s=1)), "single_h1")["ok"] is True

def test_double_h1_fails():     # ADVERSARIAL: a stub that hardcodes ok=True fails here
    r = _result(audit_html(_page(h1s=2)), "single_h1")
    assert r["ok"] is False and "2" in r["detail"]

def test_broken_jsonld_fails():
    assert _result(audit_html(_page(bad_ld=True)), "jsonld_valid")["ok"] is False

def test_clean_jsonld_passes():
    assert _result(audit_html(_page(good_ld=True, bad_ld=False)), "jsonld_valid")["ok"] is True

def test_canonical_match():
    checks = audit_html(_page(canonical="https://x.test/p"), expected_url="https://x.test/p")
    assert _result(checks, "canonical")["ok"] is True
    bad = audit_html(_page(canonical="https://x.test/other"), expected_url="https://x.test/p")
    assert _result(bad, "canonical")["ok"] is False

def test_meta_length_band():
    assert _result(audit_html(_page(meta="x"*150)), "meta_desc_len")["ok"] is True
    assert _result(audit_html(_page(meta="x"*40)), "meta_desc_len")["ok"] is False

def test_tracking_pixel_not_counted_as_missing_alt():   # only the FB pixel lacks alt -> still PASS
    assert _result(audit_html(_page(pixel=True)), "content_img_alt")["ok"] is True

def test_hreflang_reported_not_failed():   # #51 reclassified manual: report absence, do NOT fail
    r = _result(audit_html(_page()), "hreflang_en_sg")
    assert r["severity"] == "info"
