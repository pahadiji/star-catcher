#!/usr/bin/env python3
"""
Star Catcher - traffic & testing agent (runs daily in GitHub Actions).

Answers "are people finding the site, and if not, why?" with numbers:
  - visitors: the public hits.sh counter shown on the home page (today / total)
  - GitHub repo traffic: views, clones and referrers (when the token may read them)
  - mentions: links to the site on Hacker News and Reddit (search APIs, read-only)
  - badge adoption: READMEs on GitHub that embed a Star Catcher badge (backlinks)
  - site checks: home, data, a category page, a repo page and the sitemap respond

It keeps one "Growth report" issue up to date with today's numbers, a 14-day
history (stored as JSON inside the issue, so no commits are needed) and a plain
diagnosis with the next most useful action. It never posts outside this repo.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY, optional SITE_URL. Flag: --no-issue.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "pahadiji/star-catcher")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LABEL, TITLE = "growth", "Growth report"
UA = {"User-Agent": "star-catcher-traffic/1.0 (+https://github.com/%s)" % REPO}


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, name = REPO.split("/", 1)
    if name.lower() == owner.lower() + ".github.io":
        return "https://%s.github.io/" % owner.lower()
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def fetch(url, headers=None, raw=False, method="GET", body=None):
    h = dict(UA)
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h, data=data, method=method), timeout=30) as r:
            b = r.read()
            return r.status, (b.decode("utf-8", "replace") if raw else json.loads(b or b"null"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def gh(path, method="GET", body=None):
    h = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    return fetch("https://api.github.com" + path, h, method=method, body=body)


def visitors(base):
    host_path = base.replace("https://", "").rstrip("/")
    st, svg = fetch("https://hits.sh/%s.svg?view=today-total" % host_path, raw=True)
    m = re.search(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)", re.sub(r"<[^>]+>", " ", svg or ""))
    if not m:
        return None, None
    # Reading the counter counts as one hit; take ours back out.
    today, total = (int(x.replace(",", "")) for x in m.groups())
    return max(0, today - 1), max(0, total - 1)


def mentions(base):
    host = base.replace("https://", "").split("/")[0] + "/" + base.replace("https://", "").split("/", 1)[1].strip("/")
    out = []
    st, hn = fetch("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode({"query": host.split("/")[0], "restrictSearchableAttributes": "url"}))
    for h in (hn or {}).get("hits", []):
        if "star-catcher" in (h.get("url") or "") or "star-catcher" in (h.get("comment_text") or ""):
            out.append(("Hacker News", h.get("title") or "comment", "https://news.ycombinator.com/item?id=%s" % h.get("objectID")))
    st, hn2 = fetch("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode({"query": "\"%s\"" % host, "tags": "comment"}))
    for h in (hn2 or {}).get("hits", []):
        out.append(("Hacker News", "comment", "https://news.ycombinator.com/item?id=%s" % h.get("objectID")))
    st, rss = fetch("https://www.reddit.com/search.rss?" + urllib.parse.urlencode({"q": "\"%s\"" % host, "sort": "new"}), raw=True)
    for link in re.findall(r"<link href=\"(https://www\.reddit\.com/r/[^\"]+/comments/[^\"]+)\"", rss or ""):
        out.append(("Reddit", "post", link))
    seen, uniq = set(), []
    for m in out:
        if m[2] not in seen:
            seen.add(m[2])
            uniq.append(m)
    return uniq, (st == 200)


def badges(base):
    q = "%sbadge" % base.replace("https://", "")
    st, res = gh("/search/code?" + urllib.parse.urlencode({"q": "\"%s\"" % q, "per_page": 30}))
    if st != 200:
        return None, []
    repos = sorted({i["repository"]["full_name"] for i in res.get("items", []) if i["repository"]["full_name"].lower() != REPO.lower()})
    return len(repos), repos


def site_checks(base):
    out = {}
    for name, path in (("home", ""), ("data", "data/repos.json"), ("mcp list", "c/mcp-servers/"), ("advertise", "advertise/"), ("sitemap", "sitemap.xml")):
        st, _ = fetch(base + path, raw=True)
        out[name] = st
    st, sm = fetch(base + "sitemap.xml", raw=True)
    out["sitemap_urls"] = (sm or "").count("<loc>")
    return out


def diagnose(m, hist):
    tips = []
    days = len(hist)
    week = [h for h in hist if h["date"] >= (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")]
    if any(v not in (200,) for k, v in m["site"].items() if k != "sitemap_urls"):
        tips.append("**Site problem:** some pages do not return 200 (%s). Fix this first; the health check should open an issue." % ", ".join("%s=%s" % kv for kv in m["site"].items() if kv[0] != "sitemap_urls"))
    if not m["mentions"]:
        tips.append("**No one links to the site yet** (0 mentions on Hacker News or Reddit). Search engines and people find sites through links. "
                    "Post the Show HN, and reply to 2–3 threads from today's Growth leads issue.")
    if m.get("badges") == 0:
        tips.append("**No README badges yet.** Each badge is a permanent backlink. Reply under the launch posts of the repos in the leads issue with their badge link.")
    if m.get("referrers") is not None and not m["referrers"]:
        tips.append("GitHub shows no referrers to the repo either; traffic is coming only from direct visits.")
    if m.get("total") is not None and week and len(week) >= 2:
        gained = (m["total"] or 0) - (week[0].get("total") or 0)
        if gained < 30:
            tips.append("Only %d visits in the last %d days. Search traffic takes 2–6 weeks to start for a new site; "
                        "until then, visitors come only from posts and links." % (gained, len(week)))
    if days < 3:
        tips.append("Search Console: the Google verification file is live, so open Search Console, submit `sitemap.xml` and check *Pages → Indexed*.")
    return tips or ["Traffic is growing and nothing is broken. Keep posting the weekly roundup and replying to leads."]


def main():
    base = site_url()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    m = {"date": today}
    m["today"], m["total"] = visitors(base)
    st, views = gh("/repos/%s/traffic/views" % REPO)
    m["repo_views_14d"] = (views or {}).get("count") if st == 200 else None
    st, refs = gh("/repos/%s/traffic/popular/referrers" % REPO)
    m["referrers"] = [(r["referrer"], r["count"]) for r in (refs or [])] if st == 200 else None
    m["mentions"], _ = mentions(base)
    m["badges"], badge_repos = badges(base)
    m["site"] = site_checks(base)

    hist = []
    issue = None
    if TOKEN:
        st, found = gh("/repos/%s/issues?state=open&labels=%s&per_page=5" % (REPO, LABEL))
        issue = next((i for i in found or [] if i.get("title", "").startswith(TITLE)), None)
        if issue:
            mm = re.search(r"<!-- history (.*?) -->", issue.get("body") or "", re.S)
            if mm:
                try:
                    hist = json.loads(mm.group(1))
                except ValueError:
                    hist = []
    hist = [h for h in hist if h.get("date") != today][-13:] + [{"date": today, "today": m["today"], "total": m["total"],
                                                                 "mentions": len(m["mentions"]), "badges": m["badges"]}]
    tips = diagnose(m, hist)

    fmt = lambda v: "n/a" if v is None else str(v)
    rows = ["| %s | %s | %s | %s |" % (h["date"], fmt(h.get("total")), fmt(h.get("mentions")), fmt(h.get("badges"))) for h in reversed(hist)]
    body = "\n".join([
        "Updated by the traffic agent at %s. Numbers are public signals; for exact analytics add a GoatCounter code in `config.js`." % now.strftime("%Y-%m-%d %H:%M UTC"), "",
        "### Today",
        "- Site visitors (hits.sh): **%s today / %s total**" % (fmt(m["today"]), fmt(m["total"])),
        "- Repo page views on GitHub (14 days): %s" % fmt(m["repo_views_14d"]),
        "- Referrers: %s" % ("not readable with this token" if m["referrers"] is None else (", ".join("%s (%d)" % r for r in m["referrers"]) or "none")),
        "- Mentions on HN / Reddit: %d%s" % (len(m["mentions"]), "".join("\n  - %s %s: %s" % x for x in m["mentions"][:10])),
        "- READMEs with a Star Catcher badge: %s%s" % (fmt(m["badges"]), (" — " + ", ".join(badge_repos[:10])) if badge_repos else ""),
        "- Site checks: %s · sitemap URLs: %d" % (", ".join("%s %s" % (k, v) for k, v in m["site"].items() if k != "sitemap_urls"), m["site"]["sitemap_urls"]), "",
        "### Why it is or isn't being found", *("- " + t for t in tips), "",
        "### History", "| Date | Total visitors | Mentions | Badges |", "|---|---|---|---|", *rows, "",
        "<!-- history %s -->" % json.dumps(hist),
    ])
    print(body)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(body + "\n")
    if "--no-issue" in sys.argv or not TOKEN:
        return
    gh("/repos/%s/labels" % REPO, "POST", {"name": LABEL, "color": "c6ff3d", "description": "Traffic and growth report"})
    if issue:
        gh("/repos/%s/issues/%d" % (REPO, issue["number"]), "PATCH", {"body": body})
    else:
        gh("/repos/%s/issues" % REPO, "POST", {"title": TITLE, "body": body, "labels": [LABEL]})


if __name__ == "__main__":
    main()
