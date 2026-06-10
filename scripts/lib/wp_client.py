import requests
from requests.auth import HTTPBasicAuth
UID_META="ae_content_uid"
class WPClient:
    def __init__(self, api_base, user, app_password, timeout=30):
        self.base=api_base.rstrip("/")
        self.ae_base=self.base.replace("/wp/v2","/ae/v1")
        self.auth=HTTPBasicAuth(user, app_password); self.timeout=timeout
    def _get(self,path,**p):
        r=requests.get(f"{self.base}{path}",params=p,auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()
    def me(self): return self._get("/users/me")
    def find_post_by_uid(self, uid):
        r=requests.get(f"{self.ae_base}/find",params={"uid":uid},
                        auth=self.auth,timeout=self.timeout)
        if r.status_code==404: return None
        r.raise_for_status(); return r.json().get("id")
    def find_post_by_slug(self, slug):
        res=self._get("/posts",slug=slug,status="any",per_page=1)
        return res[0]["id"] if res else None
    def create_post(self, payload):
        r=requests.post(f"{self.base}/posts",json=payload,auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()["id"]
    def update_post(self, pid, payload):
        r=requests.post(f"{self.base}/posts/{pid}",json=payload,auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()["id"]
    def upload_media(self, filename, content, mime):
        r=requests.post(f"{self.base}/media",data=content,
            headers={"Content-Disposition":f'attachment; filename="{filename}"',
                     "Content-Type":mime},auth=self.auth,timeout=self.timeout)
        r.raise_for_status(); return r.json()["id"]
    def get_post(self, pid):
        return self._get(f"/posts/{pid}")
    def read_post_meta(self, pid, key):
        return self._get(f"/posts/{pid}").get("meta",{}).get(key)
    def delete_post(self, pid):
        # Fire-and-forget: callers invoke this in finally blocks (probe cleanup);
        # a cleanup failure must not raise and mask the primary result.
        requests.delete(f"{self.base}/posts/{pid}",params={"force":True},
                        auth=self.auth,timeout=self.timeout)
    def list_published_posts(self, per_page=100):
        """All published posts (type=post), following X-WP-TotalPages pagination.

        Returns a list of raw post dicts (id, slug, link, title, content,
        modified, meta, acf when exposed). acf/meta may be absent depending on
        the site's REST config — callers must treat course_id as optional.
        """
        fields = "id,slug,link,title,content,modified,meta,acf"
        posts, page = [], 1
        while True:
            r = requests.get(
                f"{self.base}/posts",
                params={"status": "publish", "per_page": per_page,
                        "page": page, "_fields": fields},
                auth=self.auth, timeout=self.timeout,
            )
            if r.status_code == 400:        # past the last page
                break
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            posts.extend(batch)
            total_pages = int(r.headers.get("X-WP-TotalPages", page) or page)
            if page >= total_pages:
                break
            page += 1
        return posts
