#!/usr/bin/env python3
"""
Star Catcher - weekly dev.to roundup (posting agent; runs with the Monday promo kit).

Publishes one article, "New Claude, MCP and agent repos this week", built from the
week's new repos and the senior agents' verified picks, with links to each repo's
Star Catcher page. dev.to allows publishing through its API with your own key, and
the article clearly says it comes from Star Catcher. Skips quietly without a key.

Secret: DEVTO_API_KEY (dev.to > Settings > Extensions > DEV Community API Keys).
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("DEVTO_API_KEY", "")


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, name = os.environ.get("GITHUB_REPOSITORY", "pahadiji/star-catcher").split("/", 1)
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def main():
    if not KEY:
        print("DEVTO_API_KEY not set; skipping the dev.to roundup.")
        return
    base = site_url()
    repos = json.load(open(os.path.join(ROOT, "data", "repos.json"))).get("repos", [])
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    fresh = sorted([r for r in repos if (r.get("created_at") or "") >= since], key=lambda r: r.get("stars") or 0, reverse=True)[:10]
    try:
        picks = json.load(open(os.path.join(ROOT, "data", "picks.json"))).get("picks", {})
    except (OSError, ValueError):
        picks = {}
    date = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines = ["Every week Star Catcher (a free map of Claude, Claude Code, MCP and agent repos on GitHub that I built) "
             "lists the new repos worth a look. Here are this week's.", "", "## Most-starred new repos", ""]
    for r in fresh:
        lines.append("- **[%s](%sr/%s/%s/)** by %s (★%d): %s" % (r["name"], base, r["owner"], r["name"], r["owner"], r.get("stars") or 0, (r.get("description") or "").strip()[:160]))
    verified = [p for items in picks.values() for p in items][:8]
    if verified:
        lines += ["", "## Verified picks", "", "New repos our scout agents tried and a senior agent approved (valid manifest, real README, licence, active):", ""]
        lines += ["- **[%s](%s)**: %s" % (p["full_name"], p["url"], p["reason"]) for p in verified]
    lines += ["", "Browse all of them as a galaxy: %s" % base]
    article = {"article": {"title": "New Claude, MCP and agent repos this week (%s)" % date, "published": True,
                           "body_markdown": "\n".join(lines), "tags": ["claude", "mcp", "ai", "opensource"], "canonical_url": base + "new/"}}
    req = urllib.request.Request("https://dev.to/api/articles", data=json.dumps(article).encode(), method="POST",
                                 headers={"api-key": KEY, "Content-Type": "application/json", "User-Agent": "star-catcher"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("dev.to:", r.status, json.loads(r.read()).get("url"))


if __name__ == "__main__":
    main()
