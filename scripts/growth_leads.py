#!/usr/bin/env python3
"""
Star Catcher - daily growth leads (runs every morning in GitHub Actions).

Finds places where people are asking about Claude Code tools, MCP servers,
skills/plugins or agent frameworks in the last 48 hours (Hacker News via the
public Algolia API, plus Reddit's public JSON when it answers), matches each
one to the most useful Star Catcher page, and lists the fastest-growing new
repos whose owners are likely to reshare their page.

It only READS other sites. It never posts, comments or replies anywhere: it
opens one "Growth leads — <date>" issue in this repo for a human (or the Claude
growth-scout routine) to review. Running it twice on the same day is a no-op.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY (set by Actions), optional SITE_URL.
Flags: --no-issue prints the report without opening an issue.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LABEL = "promo"
WINDOW_HOURS = 48
MAX_THREADS = 12
MAX_OWNERS = 6

HN_QUERIES = ["claude code", "mcp server", "model context protocol", "claude skills", "claude agent sdk",
              "anthropic agent", "agent skills", "claude plugin", "subagents"]
SUBREDDITS = ["ClaudeAI", "ClaudeCode", "mcp", "LocalLLaMA", "AI_Agents"]
TOPIC = re.compile(r"\b(claude|anthropic|mcp|model context protocol|skills?|plugins?|subagents?|agent sdk|agents?)\b", re.I)
_SEEKING = re.compile(r"\b(best|recommend\w*|which|looking for|alternatives?|vs\.?|versus|compare|comparison|favou?rite|"
                      r"what (do|are) you|how do you|any good|must[- ]have|worth (it|using|installing)|your (setup|stack|workflow)|list of|suggestions?)\b", re.I)
_TOOLISH = re.compile(r"\b(mcps?|servers?|skills?|plugins?|tools?|subagents?|agents?|extensions?|setup|stack|workflows?|frameworks?|"
                      r"cli|ide|hooks?|repos?|github)\b", re.I)


class _Asking:
    """A thread counts as a question only when it seeks tools: a seeking phrase plus a tool word."""
    @staticmethod
    def search(title):
        return _SEEKING.search(title or "") and _TOOLISH.search(title or "")


ASKING = _Asking()
CLAUDEISH = re.compile(r"\b(claude|anthropic|mcp|model context protocol|skills?\.md|claude\.md|agent skills?)\b", re.I)

# keyword -> category page slug (first match wins, so order matters)
PAGES = [
    (re.compile(r"\bmcp|model context protocol", re.I), "c/mcp-servers/", "MCP servers"),
    (re.compile(r"\bskills?\b|\bplugins?\b|slash command|hooks?\b", re.I), "c/skills-plugins/", "skills & plugins"),
    (re.compile(r"\bagent sdk|\bsubagents?|\bmulti-agent|\bframeworks?\b|\bagents?\b", re.I), "c/agents-sdk/", "agents & SDKs"),
    (re.compile(r"\bclaude\.md|prompts?\b|guides?\b|tutorial|learn", re.I), "c/prompts-guides/", "prompts & guides"),
    (re.compile(r"\bui\b|\bgui\b|desktop|\bapps?\b|vscode|neovim|editor", re.I), "c/apps-uis/", "apps & UIs"),
    (re.compile(r"\bcli\b|terminal|tools?\b|usage|cost|router|proxy", re.I), "c/dev-tools-cli/", "dev tools & CLIs"),
]


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, name = (REPO or "pahadiji/star-catcher").split("/", 1)
    if name.lower() == owner.lower() + ".github.io":
        return "https://%s.github.io/" % owner.lower()
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def get_json(url, headers=None):
    h = {"User-Agent": "star-catcher-growth-leads/1.0 (+https://github.com/%s)" % (REPO or "pahadiji/star-catcher")}
    h.update(headers or {})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt == 0:
                time.sleep(10)
                continue
            print("HTTP %s for %s" % (e.code, url))
            return None
        except Exception as e:
            print("Error %s for %s" % (e, url))
            return None
    return None


def clean(text, n=140):
    """One line, no Markdown that could ping people or break the table."""
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("|", "/").replace("@", "@​").replace("[", "(").replace("]", ")")
    return text[:n] + ("…" if len(text) > n else "")


def load_repos():
    with open(os.path.join(ROOT, "data", "repos.json")) as f:
        return json.load(f).get("repos", [])


def match_page(text, by_name, base):
    """Best Star Catcher page for a thread: a repo page if it names a tracked repo, else a category page."""
    for full in re.findall(r"github\.com/([\w.-]+/[\w.-]+)", text or ""):
        r = by_name.get(full.lower().rstrip(".").removesuffix(".git"))
        if r:
            return "%sr/%s/%s/" % (base, r["owner"], r["name"]), "repo page for %s" % r["full_name"]
    for rx, slug, label in PAGES:
        if rx.search(text or ""):
            return base + slug, "ranked list of " + label
    return base + "new/", "new repos this week"


def hn_threads(since):
    out = {}
    for q in HN_QUERIES:
        params = {"query": q, "tags": "(story,ask_hn,show_hn)", "numericFilters": "created_at_i>%d" % int(since.timestamp()), "hitsPerPage": 50}
        data = get_json("https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(params))
        for h in (data or {}).get("hits", []):
            title = h.get("title") or ""
            if not CLAUDEISH.search(title + " " + (h.get("story_text") or "")[:500]):
                continue
            oid = h.get("objectID")
            out[oid] = {
                "source": "Hacker News",
                "title": title,
                "url": "https://news.ycombinator.com/item?id=%s" % oid,
                "target": h.get("url") or "",
                "text": (h.get("story_text") or "")[:2000],
                "score": h.get("points") or 0,
                "comments": h.get("num_comments") or 0,
                "created": h.get("created_at") or "",
                "asking": title.lower().startswith("ask hn") or (not title.lower().startswith("show hn") and bool(ASKING.search(title))),
            }
            if not (out[oid]["asking"] or title.lower().startswith(("show hn", "launch hn"))):
                del out[oid]
        time.sleep(0.5)
    return list(out.values())


def reddit_threads(since):
    out, failed = [], []
    for sub in SUBREDDITS:
        data = get_json("https://www.reddit.com/r/%s/new.json?limit=100&raw_json=1" % sub)
        if data is None:
            rss = reddit_rss(sub, since)
            if rss is None:
                failed.append(sub)
            else:
                out += rss
            time.sleep(6)
            continue
        for c in (data.get("data") or {}).get("children", []):
            p = c.get("data") or {}
            created = datetime.fromtimestamp(p.get("created_utc") or 0, timezone.utc)
            title, body = p.get("title") or "", (p.get("selftext") or "")[:2000]
            if created < since or p.get("over_18") or p.get("stickied"):
                continue
            if not keep_reddit(sub, title, body) or not ASKING.search(title):
                continue
            out.append({
                "source": "r/" + sub,
                "title": title,
                "url": "https://www.reddit.com" + (p.get("permalink") or ""),
                "target": p.get("url") or "",
                "text": body,
                "score": p.get("score") or 0,
                "comments": p.get("num_comments") or 0,
                "created": created.isoformat(),
                "asking": bool(ASKING.search(title)),
            })
        time.sleep(2)
    return out, failed


def keep_reddit(sub, title, body):
    if sub in ("LocalLLaMA", "AI_Agents") and not CLAUDEISH.search(title + " " + body):
        return False
    return bool(TOPIC.search(title + " " + body))


def reddit_rss(sub, since):
    """Fallback when the JSON API refuses cloud IPs: the public Atom feed (no scores)."""
    url = "https://www.reddit.com/r/%s/new/.rss?limit=100" % sub
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "star-catcher-growth-leads/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print("RSS failed for r/%s: %s" % (sub, e))
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        title = e.findtext("a:title", "", ns)
        link = (e.find("a:link", ns).get("href") if e.find("a:link", ns) is not None else "")
        stamp = e.findtext("a:published", "", ns) or e.findtext("a:updated", "", ns)
        try:
            created = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        body = re.sub(r"<[^>]+>", " ", e.findtext("a:content", "", ns))[:2000]
        if created < since or not keep_reddit(sub, title, body) or not ASKING.search(title):
            continue
        out.append({"source": "r/" + sub, "title": title, "url": link, "target": "", "text": body,
                    "score": 0, "comments": 0, "created": created.isoformat(), "asking": bool(ASKING.search(title))})
    return out


def rising_repos(repos, already):
    now = datetime.now(timezone.utc)
    rows = []
    for r in repos:
        try:
            created = datetime.fromisoformat((r.get("created_at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        days = max((now - created).total_seconds() / 86400, 1)
        if days > 35 or (r.get("stars") or 0) < 300 or r["full_name"].lower() in already:
            continue
        rows.append((r.get("stars", 0) / days, days, r))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows[:MAX_OWNERS]


def gh(path, method="GET", body=None):
    headers = {"User-Agent": "star-catcher-growth-leads", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    data = json.dumps(body).encode() if body is not None else None
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request("https://api.github.com" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def recently_featured():
    """Repos already named in the last 14 days of promo issues, so owners are not pitched twice."""
    if not (REPO and TOKEN):
        return set()
    since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _, issues = gh("/repos/%s/issues?state=all&labels=%s&since=%s&per_page=30" % (REPO, LABEL, since))
    seen = set()
    for i in issues or []:
        for full in re.findall(r"github\.com/([\w.-]+/[\w.-]+)", i.get("body") or ""):
            seen.add(full.lower())
    return seen


def main():
    base = site_url()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=WINDOW_HOURS)
    today = now.strftime("%Y-%m-%d")
    title = "Growth leads — %s" % today
    repos = load_repos()
    by_name = {r["full_name"].lower(): r for r in repos}

    threads = hn_threads(since)
    rd, reddit_failed = reddit_threads(since)
    threads += rd
    # Questions first, then by engagement.
    threads.sort(key=lambda t: (t["asking"], t["comments"] + t["score"] / 4), reverse=True)
    threads = threads[:MAX_THREADS]

    lines = ["Daily growth leads for **%s** (last %d hours). Collected automatically; nothing was posted anywhere." % (today, WINDOW_HOURS), "",
             "Reply by hand, answer the question first, link one page at most, and say \"I made this\" when you link the site.", ""]
    lines += ["### Threads", ""]
    if threads:
        lines += ["| # | Where | Thread | Kind | Engagement | Page to link |", "|---|---|---|---|---|---|"]
        for n, t in enumerate(threads, 1):
            page, why = match_page(" ".join([t["title"], t["target"], t["text"]]), by_name, base)
            kind = "question" if t["asking"] else "launch/news"
            lines.append("| %d | %s | [%s](%s) | %s | %d pts · %d comments | %s (%s) |" % (
                n, t["source"], clean(t["title"], 110), t["url"], kind, t["score"], t["comments"], page, why))
    else:
        lines.append("No matching threads in the last %d hours." % WINDOW_HOURS)
    if reddit_failed:
        lines += ["", "_Reddit did not answer for: %s (it often blocks cloud IPs). Check those subs by hand._" % ", ".join("r/" + s for s in reddit_failed)]

    owners = rising_repos(repos, recently_featured())
    lines += ["", "### Owners to tell (fastest-growing new repos, not pitched in the last 14 days)", ""]
    if owners:
        lines += ["| Repo | Stars | Stars/day | Age | Page | Badge |", "|---|---|---|---|---|---|"]
        for rate, days, r in owners:
            lines.append("| [%s](https://github.com/%s) | %d | %d | %dd | %sr/%s/%s/ | `%sbadge/%s/%s.svg` |" % (
                r["full_name"], r["full_name"], r.get("stars", 0), rate, days, base, r["owner"], r["name"], base, r["owner"], r["name"]))
        lines += ["", "Reply under the owner's own launch post with their page and badge. Never open issues on their repos."]
    else:
        lines.append("None today.")

    body = "\n".join(lines)
    print(body)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(body + "\n")
    if "--no-issue" in sys.argv or not (REPO and TOKEN):
        return
    _, open_today = gh("/repos/%s/issues?state=all&labels=%s&per_page=20" % (REPO, LABEL))
    if any((i.get("title") or "") == title for i in open_today or []):
        print("Issue %r already exists; not opening another." % title)
        return
    gh("/repos/%s/labels" % REPO, "POST", {"name": LABEL, "color": "a77bff", "description": "Promotion and growth"})
    status, made = gh("/repos/%s/issues" % REPO, "POST", {"title": title, "body": body, "labels": [LABEL]})
    print(status, (made or {}).get("html_url"))


if __name__ == "__main__":
    main()
