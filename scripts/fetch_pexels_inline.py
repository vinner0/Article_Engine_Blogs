"""One-shot Pexels fetcher used by ae-6 when image placeholders need resolving.
Reads PEXELS_API_KEY from .env, downloads one image per (query,filename) tuple.
Idempotent: skips files that already exist."""
import os, sys, pathlib, re, urllib.request, urllib.parse, json

def load_env(p):
    env={}
    for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env

def fetch_one(api_key, query, out_path, orientation="landscape"):
    q=urllib.parse.urlencode({"query":query,"per_page":3,"orientation":orientation})
    url=f"https://api.pexels.com/v1/search?{q}"
    req=urllib.request.Request(url, headers={"Authorization":api_key,
        "User-Agent":"ae-bot/1.0 (article-engine)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data=json.loads(r.read().decode())
    photos=data.get("photos") or []
    if not photos:
        raise RuntimeError(f"no pexels result for: {query}")
    photo=photos[0]
    img_url=photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
    dl_req=urllib.request.Request(img_url, headers={"User-Agent":"ae-bot/1.0 (article-engine)"})
    with urllib.request.urlopen(dl_req, timeout=60) as r:
        out_path.write_bytes(r.read())
    return {"file":str(out_path),"photographer":photo.get("photographer"),
            "src_url":img_url,"pexels_url":photo.get("url"),"id":photo.get("id")}

def main():
    repo=pathlib.Path(__file__).resolve().parent.parent
    env=load_env(repo/".env")
    key=env.get("PEXELS_API_KEY")
    if not key:
        sys.exit("PEXELS_API_KEY missing from .env")
    slug=sys.argv[1]
    spec_path=repo/"content"/"trainingint"/slug/"_draft"/"pexels-queries.json"
    spec=json.loads(spec_path.read_text(encoding="utf-8"))
    images_dir=repo/"content"/"trainingint"/slug/"images"; images_dir.mkdir(parents=True, exist_ok=True)
    log=[]
    for item in spec:
        out=images_dir/item["file"]
        if out.exists() and out.stat().st_size>0:
            log.append({"file":str(out),"skipped":True}); continue
        meta=fetch_one(key, item["query"], out, orientation=item.get("orientation","landscape"))
        log.append(meta); print("OK", out.name, "<-", item["query"])
    (images_dir/"_pexels-log.json").write_text(json.dumps(log,indent=2),encoding="utf-8")
    print("DONE", len(log), "images for", slug)

if __name__=="__main__":
    main()
