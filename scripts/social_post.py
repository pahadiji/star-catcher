#!/usr/bin/env python3
"""
Star Catcher - automatic social posts (optional, runs after each 6-hour scan).

Posts ONE highlight per scan (at most 4 a day) about the best newly found repo
to Bluesky and/or Mastodon, both of which allow clearly-labelled automated
accounts. It never repeats a repo (state kept in promo/posted.json).
X/Twitter and Reddit are left to the weekly promo kit: their rules and API
pricing make unattended posting a ban risk.

Secrets (all optional; a network is skipped when its secrets are missing):
  BLUESKY_HANDLE, BLUESKY_APP_PASSWORD      (Settings > App passwords on bsky.app)
  MASTODON_URL, MASTODON_TOKEN              (e.g. https://mastodon.social, token with write:statuses)
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "promo", "posted.json")


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, name = os.environ.get("GITHUB_REPOSITORY", "pahadiji/star-catcher").split("/", 1)
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def call(url, body=None, headers=None, method="POST"):
    h = {"Content-Type": "application/json", "User-Agent": "star-catcher"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def fmt(n):
    return ("%dk" % round(n / 1000)) if n >= 10000 else ("%.1fk" % (n / 1000)) if n >= 1000 else str(n)


def post_bluesky(text, link):
    handle, pw = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and pw):
        return "bluesky: not configured"
    s = call("https://bsky.social/xrpc/com.atproto.server.createSession", {"identifier": handle, "password": pw})
    b = text.encode("utf-8")
    start = b.find(link.encode("utf-8"))
    facets = [{"index": {"byteStart": start, "byteEnd": start + len(link.encode("utf-8"))},
               "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}]}] if start >= 0 else []
    record = {"$type": "app.bsky.feed.post", "text": text, "facets": facets, "langs": ["en"],
              "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    call("https://bsky.social/xrpc/com.atproto.repo.createRecord", {"repo": s["did"], "collection": "app.bsky.feed.post", "record": record},
         {"Authorization": "Bearer " + s["accessJwt"]})
    return "bluesky: posted"


def post_mastodon(text):
    url, token = os.environ.get("MASTODON_URL"), os.environ.get("MASTODON_TOKEN")
    if not (url and token):
        return "mastodon: not configured"
    call(url.rstrip("/") + "/api/v1/statuses", {"status": text, "visibility": "public", "language": "en"}, {"Authorization": "Bearer " + token})
    return "mastodon: posted"


def main():
    with open(os.path.join(ROOT, "data", "repos.json")) as f:
        repos = json.load(f).get("repos", [])
    try:
        with open(STATE) as f:
            posted = json.load(f)
    except Exception:
        posted = {"ids": []}
    week = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    pool = [r for r in repos if (r.get("created_at") or "") >= week and str(r["id"]) not in posted["ids"]]
    if not pool:
        print("nothing new to post")
        return
    r = max(pool, key=lambda x: x.get("stars") or 0)
    link = "%sr/%s/%s/" % (site_url(), r["owner"], r["name"])
    desc = (r.get("description") or "").strip()
    if len(desc) > 140:
        desc = desc[:137].rsplit(" ", 1)[0] + "…"
    text = "New star in the Claude galaxy: %s by %s (★%s)\n%s\n%s\n#ClaudeAI #ClaudeCode #MCP" % (r["name"], r["owner"], fmt(r.get("stars") or 0), desc, link)
    results = []
    for fn in (lambda: post_bluesky(text, link), lambda: post_mastodon(text)):
        try:
            results.append(fn())
        except Exception as e:
            results.append("error: %s" % e)
    print("\n".join(results))
    if any(x.endswith("posted") for x in results):
        posted["ids"] = (posted["ids"] + [str(r["id"])])[-2000:]
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as f:
            json.dump(posted, f)


if __name__ == "__main__":
    main()
