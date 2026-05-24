"""Reusable HTML blocks for the SEO pass and backfill regeneration: a peak-intent
course card and a hand-picked Related-Articles list. Inline styles are used on the
card so it renders correctly without depending on theme CSS; the `ae-course-card` /
`ae-related` classes are kept as hooks if the theme later styles them.

Price and next-intake are deliberately NOT parameters — they change often and would
go stale in source; the card's CTA links to the live course page where those are
authoritative."""
import html as _html

def render_course_card(title, url, funding, cta_label="Register", subtitle=None):
    sub = f'<p style="margin:6px 0 12px;color:#444;">{_html.escape(subtitle)}</p>' if subtitle else ""
    return (
        '<div class="ae-course-card" style="border:1px solid #d8e0ea;border-left:4px solid '
        '#1f5fa8;border-radius:6px;padding:18px 20px;margin:28px 0;background:#f7faff;">'
        '<span style="display:inline-block;background:#1f5fa8;color:#fff;font-size:12px;'
        f'font-weight:600;padding:3px 10px;border-radius:12px;">{_html.escape(funding)}</span>'
        f'<h3 style="margin:10px 0 4px;">{_html.escape(title)}</h3>'
        f'{sub}'
        f'<a href="{_html.escape(url, quote=True)}" style="display:inline-block;background:'
        '#1f5fa8;color:#fff;text-decoration:none;font-weight:600;padding:10px 22px;'
        f'border-radius:5px;">{_html.escape(cta_label)}</a></div>'
    )

def render_related(items):
    """items: list of (label, url). Returns a styled Related-Articles block, or '' when empty."""
    if not items:
        return ""
    lis = "".join(
        f'<li><a href="{_html.escape(u, quote=True)}">{_html.escape(label)}</a></li>'
        for label, u in items
    )
    return (
        '<aside class="ae-related" style="margin:32px 0;padding:16px 20px;border-top:'
        '2px solid #e3e8ef;"><p><strong>Related articles</strong></p>'
        f'<ul>{lis}</ul></aside>'
    )
