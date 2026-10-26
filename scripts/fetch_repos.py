#!/usr/bin/env python3
"""
Star Catcher - data updater.
Searches GitHub for Claude-related repositories, merges them with the
existing dataset, tags new/updated ones and writes data/repos.json.
Runs every 6 hours via GitHub Actions (no external dependencies).
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "data", "repos.json")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_REPOS = 3000          # cap on stored repos
PAGES_PER_QUERY = 3       # 100 results per page
MIN_STARS = 2             # skip empty/spam repos

# Search queries (GitHub search syntax)
QUERIES = [
    "claude-code in:name,description,topics",
    "\"claude code\" in:name,description,readme",
    "topic:claude",
    "topic:claude-code",
    "topic:anthropic",
    "topic:claude-ai",
    "\"anthropic claude\" in:description",
    "mcp claude in:name,description,topics",
    "claude skills in:name,description",
    "claude agent sdk in:name,description",
    "claude subagents in:name,description",
    "claude plugin in:name,description",
]

CATEGORIES = [
    ("MCP Servers", ["mcp", "model context protocol", "mcp-server"]),
    ("Skills & Plugins", ["skill", "plugin", "slash command", "hooks"]),
    ("Agents & SDK", ["agent", "sdk", "subagent", "autonomous", "multi-agent"]),
    ("Prompts & Guides", ["prompt", "awesome", "guide", "tutorial", "cookbook", "course", "claude.md"]),
    ("Apps & UIs", ["ui", "app", "desktop", "chat", "web", "gui", "extension", "vscode", "nvim"]),
    ("Dev Tools & CLI", ["cli", "tool", "terminal", "proxy", "router", "usage", "monitor"]),
]


def api(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "claude-repo-finder"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):  # rate limited: wait and retry
                time.sleep(30 * (attempt + 1))
                continue
            print(f"HTTP {e.code} for {url}")
            return None
        except Exception as e:
            print(f"Error {e} for {url}")
            time.sleep(5)
    return None


RELEVANT = ("claude", "anthropic", "mcp", "model context protocol", "model-context-protocol")


# Never list these: adult/NSFW content and common spam keywords (keeps the site ad-network safe).
BLOCKED = ("nsfw", "porn", "hentai", "nude", "nudity", "nudify", "sexual", "sex ", "onlyfans", "xxx", "erotic",
           "undress", "deepnude", "casino", "gambling", "betting", "keygen", "crack ", "cracked", "warez")


def blocked(repo):
    text = " ".join([repo.get("full_name") or "", repo.get("description") or "", " ".join(repo.get("topics") or [])]).lower() + " "
    return repo.get("owner") == "sample" or any(k in text for k in BLOCKED)


def relevant(repo):
    """Keep only repos that actually mention Claude, Anthropic or MCP.
    GitHub search matches loosely (README text, single words), which lets
    unrelated giant repos in; this check looks at name, description and topics."""
    text = " ".join([
        repo.get("full_name") or repo.get("name") or "",
        repo.get("description") or "",
        " ".join(repo.get("topics") or []),
    ]).lower()
    return any(k in text for k in RELEVANT)


def categorize(repo):
    text = " ".join([
        repo.get("name") or "",
        repo.get("description") or "",
        " ".join(repo.get("topics") or []),
    ]).lower()
    for cat, words in CATEGORIES:
        if any(w in text for w in words):
            return cat
    return "Other"


def slim(r):
    return {
        "id": r["id"],
        "name": r["name"],
        "full_name": r["full_name"],
        "owner": r["owner"]["login"],
        "avatar": r["owner"]["avatar_url"],
        "url": r["html_url"],
        "description": (r.get("description") or "")[:300],
        "stars": r.get("stargazers_count", 0),
        "forks": r.get("forks_count", 0),
        "language": r.get("language"),
        "topics": (r.get("topics") or [])[:8],
        "license": (r.get("license") or {}).get("spdx_id"),
        "created_at": r.get("created_at"),
        "pushed_at": r.get("pushed_at"),
        "updated_at": r.get("updated_at"),
        "homepage": r.get("homepage"),
    }


def main():
    now = datetime.now(timezone.utc)
    existing = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                old_data = json.load(f)
            # Sample/demo data is not a real previous scan: start fresh so the
            # first real import is not tagged as hundreds of "new" repos.
            if not old_data.get("sample"):
                for r in old_data.get("repos", []):
                    existing[r["id"]] = r
        except Exception:
            pass

    # Only fetch repos pushed in the last 30 days on refresh runs; full scan on first run
    since = (now - timedelta(days=30)).strftime("%Y-%m-%d") if existing else None

    found = {}
    for q in QUERIES:
        query = f"{q} stars:>={MIN_STARS} fork:false archived:false"
        if since:
            query += f" pushed:>={since}"
        for sort in ("stars", "updated"):
            for page in range(1, PAGES_PER_QUERY + 1):
                url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
                    {"q": query, "sort": sort, "order": "desc", "per_page": 100, "page": page}
                )
                data = api(url)
                time.sleep(2.2 if TOKEN else 6.5)  # stay under search rate limit
                if not data or not data.get("items"):
                    break
                for r in data["items"]:
                    item = slim(r)
                    if relevant(item) and not blocked(item):
                        found[r["id"]] = item
                if len(data["items"]) < 100:
                    break
        print(f"{q!r}: total unique so far {len(found)}")

    new_ids, updated_ids = [], []
    for rid, r in found.items():
        old = existing.get(rid)
        if old is None:
            # On the very first import every repo would look "new"; use its creation
            # date instead so only repos found by later scans get the NEW tag.
            r["first_seen"] = now.isoformat() if existing else (r.get("created_at") or now.isoformat())
            new_ids.append(rid)
        else:
            r["first_seen"] = old.get("first_seen", now.isoformat())
            if r["pushed_at"] != old.get("pushed_at"):
                updated_ids.append(rid)
        existing[rid] = r

    repos = [r for r in existing.values() if relevant(r) and not blocked(r)]
    for r in repos:
        r["category"] = categorize(r)
    repos.sort(key=lambda r: r["stars"], reverse=True)
    repos = repos[:MAX_REPOS]

    out = {
        "last_updated": now.isoformat(),
        "total": len(repos),
        "new_this_run": len(new_ids),
        "updated_this_run": len(updated_ids),
        "repos": repos,
    }
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Saved {len(repos)} repos | new: {len(new_ids)} | updated: {len(updated_ids)}")


if __name__ == "__main__":
    main()
