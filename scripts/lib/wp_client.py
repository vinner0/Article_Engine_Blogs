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
    def read_post_meta(self, pid, key):
        return self._get(f"/posts/{pid}").get("meta",{}).get(key)
    def delete_post(self, pid):
        # Fire-and-forget: callers invoke this in finally blocks (probe cleanup);
        # a cleanup failure must not raise and mask the primary result.
        requests.delete(f"{self.base}/posts/{pid}",params={"force":True},
                        auth=self.auth,timeout=self.timeout)
