"""Local review/approval dashboard for staged ae-5 improvements.

    python -m scripts.review_server        # -> http://127.0.0.1:5001

Shows every pending `_improve/04-seo.html` with a word-level before/after diff,
an editable HTML box, and Approve / Reject buttons. Approve runs
apply_improvement (republish live, or update the scheduled draft); Reject deletes
the staging. Local-only (binds 127.0.0.1) — Approve performs real WordPress writes.
"""
import io
import pathlib
import contextlib

from flask import Flask, request, redirect, url_for, flash, render_template_string
from markupsafe import Markup

from scripts.lib import review
from scripts import apply_improvement

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITES = ["trainingint"]

app = Flask(__name__)
app.secret_key = "ae-review-local"  # local-only tool; not exposed to the network

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>AE Review</title>
<style>
  body{font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1a1a1a}
  h1{font-size:22px} .sub{color:#666;margin:-6px 0 22px}
  .card{border:1px solid #ddd;border-radius:10px;padding:18px 20px;margin:18px 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}
  .title{font-size:18px;font-weight:600;margin:0 0 4px}
  .meta{color:#666;font-size:13px;margin-bottom:6px}
  .meta a{color:#2557d6;text-decoration:none} .meta a:hover{text-decoration:underline}
  .pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;background:#eef;color:#335;margin-left:6px}
  .diff{background:#fafafa;border:1px solid #eee;border-radius:8px;padding:12px 14px;margin:12px 0;font-size:14px}
  .hunk{padding:6px 0;border-bottom:1px dashed #eee} .hunk:last-child{border:0}
  .tag{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:#999;margin-right:8px}
  del{background:#ffe3e3;color:#a11;text-decoration:line-through;padding:0 2px;border-radius:3px}
  ins{background:#dcffe0;color:#161;text-decoration:none;padding:0 2px;border-radius:3px}
  textarea{width:100%;height:320px;font:12px/1.5 ui-monospace,Consolas,monospace;border:1px solid #ccc;border-radius:6px;padding:10px;box-sizing:border-box}
  details{margin:10px 0} summary{cursor:pointer;color:#2557d6;font-size:14px}
  .row{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
  button{font:14px sans-serif;padding:8px 16px;border:0;border-radius:7px;cursor:pointer}
  .approve{background:#1a7f37;color:#fff} .reject{background:#fff;color:#a11;border:1px solid #e3b3b3}
  .save{background:#2557d6;color:#fff}
  .flash{background:#f3f7ff;border:1px solid #cdddff;border-radius:8px;padding:10px 14px;margin:14px 0;white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace}
  .empty{color:#888;padding:40px 0;text-align:center}
  .nochanges{color:#999;font-style:italic}
</style></head><body>
<h1>Article improvements awaiting review</h1>
<div class="sub">{{ pending|length }} staged · Approve posts to WordPress (live republish, or updates the scheduled draft) · Reject discards</div>
{% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}
{% if not pending %}<div class="empty">Nothing staged right now. The nightly run will drop improvements here.</div>{% endif %}
{% for p in pending %}
  <div class="card">
    <div class="title">{{ p.title }}</div>
    <div class="meta">
      <code>{{ p.slug }}</code><span class="pill">{{ p.status }}{% if p.status=='scheduled' and p.scheduled_date %} · publishes {{ p.scheduled_date }}{% endif %}</span>
      {% if p.url %} · <a href="{{ p.url }}" target="_blank">view live (before)</a>{% endif %}
      {% if p.edit_url %} · <a href="{{ p.edit_url }}" target="_blank">edit in WordPress</a>{% endif %}
    </div>
    <div class="diff">
      {% if p.blocks %}
        {% for b in p.blocks %}<div class="hunk"><span class="tag">{{ b.type }}</span>{{ b.html }}</div>{% endfor %}
      {% else %}<span class="nochanges">No text changes vs current draft.</span>{% endif %}
    </div>
    <details>
      <summary>Edit the full HTML before approving</summary>
      <form method="post" action="{{ url_for('save') }}">
        <input type="hidden" name="site" value="{{ p.site }}"><input type="hidden" name="slug" value="{{ p.slug }}">
        <textarea name="content">{{ p.after }}</textarea>
        <div class="row"><button class="save" type="submit">Save edits</button></div>
      </form>
    </details>
    <div class="row">
      <form method="post" action="{{ url_for('approve') }}" onsubmit="return confirm('Approve and post to WordPress?\n\n{{ p.slug }}');">
        <input type="hidden" name="site" value="{{ p.site }}"><input type="hidden" name="slug" value="{{ p.slug }}">
        <button class="approve" type="submit">✓ Approve &amp; post</button>
      </form>
      <form method="post" action="{{ url_for('reject') }}" onsubmit="return confirm('Discard this improvement?\n\n{{ p.slug }}');">
        <input type="hidden" name="site" value="{{ p.site }}"><input type="hidden" name="slug" value="{{ p.slug }}">
        <button class="reject" type="submit">✗ Reject</button>
      </form>
    </div>
  </div>
{% endfor %}
</body></html>
"""


def _pending_with_diffs():
    rows = review.list_pending(ROOT, SITES)
    for r in rows:
        before, after = review.read_pair(ROOT, r["site"], r["slug"])
        r["after"] = after
        r["blocks"] = [{**b, "html": Markup(b["html"])} for b in review.diff_blocks(before, after)]
    return rows


@app.route("/")
def index():
    return render_template_string(PAGE, pending=_pending_with_diffs())


@app.route("/save", methods=["POST"])
def save():
    site, slug = request.form["site"], request.form["slug"]
    try:
        review.save_improve(ROOT, site, slug, request.form.get("content", ""))
        flash(f"Saved your edits to {slug}. Diff below now reflects them.")
    except Exception as e:
        flash(f"Save failed for {slug}: {e}")
    return redirect(url_for("index"))


@app.route("/approve", methods=["POST"])
def approve():
    site, slug = request.form["site"], request.form["slug"]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            apply_improvement.run(site, [slug])
        flash(f"Approved {slug} -> posted.\n\n{buf.getvalue().strip()}")
    except Exception as e:
        flash(f"Approve FAILED for {slug}: {e}\n\n{buf.getvalue().strip()}")
    return redirect(url_for("index"))


@app.route("/reject", methods=["POST"])
def reject():
    site, slug = request.form["site"], request.form["slug"]
    removed = review.reject(ROOT, site, slug)
    flash(f"Rejected {slug} — staging discarded." if removed else f"Nothing to reject for {slug}.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    print("AE review dashboard -> http://127.0.0.1:5001  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5001, debug=False)
