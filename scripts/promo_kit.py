#!/usr/bin/env python3
"""
Star Catcher - weekly promo kit (runs every Monday).

Writes ready-to-post copy for the places where posting by hand works best
(X, Reddit, LinkedIn, Hacker News, your newsletter) using this week's new repos,
and opens it as a GitHub issue so you can copy, tweak and post in a few minutes.
It also lists the owners of the top new repos: tagging them is the single best
way to get reshares.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, name = (REPO or "pahadiji/star-catcher").split("/", 1)
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def fmt(n):
    return ("%dk" % round(n / 1000)) if n >= 10000 else ("%.1fk" % (n / 1000)) if n >= 1000 else str(n)


def main():
    base = site_url()
    with open(os.path.join(ROOT, "data", "repos.json")) as f:
        data = json.load(f)
    repos = data.get("repos", [])
    week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    fresh = sorted([r for r in repos if (r.get("first_seen") or "") >= week], key=lambda r: r.get("stars") or 0, reverse=True)
    top = fresh[:10]
    date = datetime.now(timezone.utc).strftime("%d %b %Y")
    page = lambda r: "%sr/%s/%s/" % (base, r["owner"], r["name"])
    short = lambda r: ((r.get("description") or "").strip()[:110])

    x_thread = ["%d new Claude / Claude Code / MCP repos showed up on GitHub this week. The best ones 🧵\n\n(Explore all %d as a galaxy: %s)" % (len(fresh), len(repos), base)]
    x_thread += ["%d. %s by @%s — %s ★%s\n%s" % (i + 1, r["name"], r["owner"], short(r), fmt(r.get("stars") or 0), page(r)) for i, r in enumerate(top[:5])]
    reddit = "**This week's new Claude repos (%s)**\n\nI built a free site that tracks every Claude Code, MCP server, skill and agent repo on GitHub and refreshes every 6 hours. %d new ones this week. Top picks:\n\n%s\n\nFull list: %snew/ — the galaxy view lets you browse all %d repos by category. Feedback welcome." % (
        date, len(fresh), "\n".join("- **[%s](%s)** by %s — %s (★%s)" % (r["name"], page(r), r["owner"], short(r), fmt(r.get("stars") or 0)) for r in top), base, len(repos))
    linkedin = "Claude's open-source ecosystem is moving fast: %d new Claude Code, MCP and agent repos appeared on GitHub this week.\n\nThree worth a look:\n%s\n\nI track all %d of them (updated every 6 hours) at %s\n\n#ClaudeAI #AIagents #MCP #DeveloperTools" % (
        len(fresh), "\n".join("• %s — %s %s" % (r["name"], short(r), page(r)) for r in top[:3]), len(repos), base)
    newsletter = "## New Claude repos — week of %s\n\n%s\n\nBrowse everything: %s" % (date, "\n".join("%d. [%s](%s) by %s — %s" % (i + 1, r["name"], page(r), r["owner"], short(r)) for i, r in enumerate(top)), base)
    owners = "\n".join("- [ ] @%s — https://github.com/%s/%s (★%s) — tell them they're featured; their badge: %sbadge/%s/%s.svg" % (r["owner"], r["owner"], r["name"], fmt(r.get("stars") or 0), base, r["owner"], r["name"]) for r in top)

    body = """Promo kit for the week of **{date}** — {n} new repos, {total} tracked. Copy, adjust, post. Takes about 10 minutes.

### 1. X / Twitter thread (post as a thread; tag owners)
{x}

### 2. Reddit (r/ClaudeAI, r/ClaudeCode, r/mcp — check each sub's self-promotion rules; space posts a few days apart)
{reddit}

### 3. LinkedIn
{linkedin}

### 4. Newsletter section
{newsletter}

### 5. Tell the featured owners (best reshare rate)
Reply to their launch post or tweet with their page link. Do not open issues on their repos.
{owners}

### One-time launches (tick when done)
- [ ] Show HN: "Show HN: Star Catcher – every Claude/MCP repo on GitHub as an explorable galaxy"
- [ ] Product Hunt launch
- [ ] Submit to awesome-claude-code / awesome-mcp-servers lists (as a resource, via pull request)
- [ ] Google Search Console: add the site and submit {base}sitemap.xml
- [ ] Bing Webmaster Tools: add the site (IndexNow pings already run every 6 hours)
""".format(date=date, n=len(fresh), total=len(repos), x="\n\n---\n\n".join("```\n%s\n```" % t for t in x_thread), reddit="```markdown\n%s\n```" % reddit,
           linkedin="```\n%s\n```" % linkedin, newsletter="```markdown\n%s\n```" % newsletter, owners=owners or "- none this week", base=base)
    os.makedirs(os.path.join(ROOT, "promo"), exist_ok=True)
    with open(os.path.join(ROOT, "promo", "latest-kit.md"), "w") as f:
        f.write(body)
    print(body[:1500])
    if REPO and TOKEN:
        def gh(path, payload):
            req = urllib.request.Request("https://api.github.com" + path, data=json.dumps(payload).encode(), method="POST",
                                         headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json", "User-Agent": "star-catcher"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.status
            except Exception as e:
                return str(e)
        gh("/repos/%s/labels" % REPO, {"name": "promo", "color": "a77bff", "description": "Weekly promo kit"})
        print(gh("/repos/%s/issues" % REPO, {"title": "Promo kit — week of %s" % date, "body": body, "labels": ["promo"]}))


if __name__ == "__main__":
    main()
