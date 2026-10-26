#!/usr/bin/env python3
"""
Star Catcher - tell search engines about new pages right away (IndexNow).

After each scan, sends the pages of newly found repos plus the list pages to
IndexNow, which shares them with Bing, Yandex, Seznam, Naver and others.
(Google does not use IndexNow; it reads sitemap.xml - submit that once in
Google Search Console.) Safe to run anywhere; it does nothing without changes.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "5f0c3e9a2b7d4c18a6e1f9b3d2c4a7e8"   # public by design; the matching file is <KEY>.txt at the site root


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, name = os.environ.get("GITHUB_REPOSITORY", "pahadiji/star-catcher").split("/", 1)
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def main():
    base = site_url()
    with open(os.path.join(ROOT, "data", "repos.json")) as f:
        data = json.load(f)
    since = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    fresh = [r for r in data.get("repos", []) if (r.get("first_seen") or "") >= since]
    urls = [base, base + "new/"] + ["%sc/%s/" % (base, s) for s in ("mcp-servers", "agents-sdk", "skills-plugins", "dev-tools-cli", "prompts-guides", "apps-uis", "other")]
    urls += ["%sr/%s/%s/" % (base, r["owner"], r["name"]) for r in fresh[:9000]]
    body = json.dumps({"host": urlparse(base).netloc, "key": KEY, "keyLocation": base + KEY + ".txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("IndexNow accepted %d urls (HTTP %s)" % (len(urls), r.status))
    except Exception as e:
        print("IndexNow ping skipped: %s" % e)   # never fail the data update because of this


if __name__ == "__main__":
    main()
