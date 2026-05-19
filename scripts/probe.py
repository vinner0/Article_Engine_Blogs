"""P0 design-gating preflight. Probes the LIVE site; writes results into
config/sites.yaml. Runtime facts come from the target, never assumed."""
import os, sys, yaml, pathlib, datetime, uuid
from dotenv import load_dotenv
from scripts.lib.wp_client import WPClient
ROOT=pathlib.Path(__file__).resolve().parents[1]

def probe_meta_writable(wp, meta_key, token):
    pid=wp.create_post({"title":"AE PROBE del","status":"draft",
                        "content":"<p>x</p>","meta":{meta_key:token}})
    try:
        wp.update_post(pid,{"meta":{meta_key:token}})
        return wp.read_post_meta(pid,meta_key)==token
    finally:
        wp.delete_post(pid)

def probe_uid_roundtrip(wp):
    """Prove the idempotency mechanism on the LIVE site: write ae_content_uid,
    then resolve it back via the helper /ae/v1/find route."""
    tok="probe-"+uuid.uuid4().hex[:10]
    pid=wp.create_post({"title":"AE UID PROBE","status":"draft",
                        "content":"<p>x</p>","meta":{"ae_content_uid":tok}})
    try:
        return wp.find_post_by_uid(tok)==pid
    finally:
        wp.delete_post(pid)

def detect_seo_plugin(wp):
    try:
        s=wp._get("/posts",per_page=1); meta=(s[0].get("meta",{}) if s else {})
        if any(k.startswith("rank_math") for k in meta): return "rankmath"
        if any(k.startswith("_yoast") for k in meta): return "yoast"
    except Exception: pass
    return "none"

def run(site="trainingint"):
    load_dotenv(ROOT/"credentials/.env")
    cfg=yaml.safe_load((ROOT/"config/sites.yaml").read_text())
    s=cfg["sites"][site]
    pw=os.environ.get(s["app_password_env"]); user=os.environ.get(s["app_password_env"]+"_USER")
    if not pw or not user:
        sys.exit(f"Set {s['app_password_env']} and {s['app_password_env']}_USER in credentials/.env")
    wp=WPClient(s["wp_api_base"],user,pw); p=s["probe"]
    try: wp.me(); p["rest_ok"]=True
    except Exception as e: p["rest_ok"]=False; print("REST/auth FAILED:",e)
    if p["rest_ok"]:
        try: p["uid_roundtrip_ok"]=probe_uid_roundtrip(wp)
        except Exception as e: p["uid_roundtrip_ok"]=False; print("UID roundtrip FAILED (helper plugin installed?):",e)
        plugin=detect_seo_plugin(wp); p["seo_plugin"]=plugin
        mk={"rankmath":"rank_math_title","yoast":"_yoast_wpseo_title"}.get(plugin)
        p["seo_meta_rest_writable"]=probe_meta_writable(wp,mk,"AE-PROBE-TOK") if mk else False
    p["probed_at"]=datetime.date.today().isoformat()
    (ROOT/"config/sites.yaml").write_text(yaml.safe_dump(cfg,sort_keys=False))
    print("PROBE:",yaml.safe_dump(p,sort_keys=False))
    print("\nMANUAL items to fill in config/sites.yaml before first batch:")
    print(" html_renders_ok, wpcron_reliable, default_category_id,")
    print(" default_author_id, keyword_data (ubersuggest_csv|ai_only)")

if __name__=="__main__":
    run(sys.argv[1] if len(sys.argv)>1 else "trainingint")
