#!/usr/bin/env python3
"""
Star Catcher - talent scouts (runs daily in GitHub Actions, before the senior agents).

Three scouts search GitHub for promising new work and "demo" each candidate:
  skills scout   - Claude / agent skills (a SKILL.md with name + description)
  plugins scout  - Claude Code plugins and marketplaces (.claude-plugin/*.json)
  repos scout    - MCP servers, agents built on the Claude Agent SDK, and other Claude tools

The demo is a static inspection: the scout downloads the repo's file list and the
one manifest that proves what it is (SKILL.md, plugin.json, package.json,
pyproject.toml...), validates it, and scores README, licence, activity and stars.
It never runs third-party code. Results go to data/scouted.json, which the senior
agents (scripts/seniors.py) review.

Env: GITHUB_TOKEN. Flags: --dry-run prints results without writing.
"""
import base64
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "scouted.json")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PER_SCOUT = int(os.environ.get("SCOUT_LIMIT", "25"))  # candidates demoed per scout per run
KEEP = 400              # scouted records kept

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_repos import BLOCKED, categorize  # noqa: E402  (shared rules)

SCOUTS = {
    "skills": ["topic:claude-skills", "topic:agent-skills", "topic:claude-code-skills", "\"SKILL.md\" claude in:readme"],
    "plugins": ["topic:claude-code-plugin", "topic:claude-plugin", "\"claude code plugin\" in:name,description,readme", "\"plugin marketplace\" claude in:readme"],
    "repos": ["topic:mcp-server claude", "\"mcp server\" claude in:name,description", "\"claude agent sdk\" in:readme,description", "claude-code in:name,description,topics"],
}


def api(url, raw=False):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "star-catcher-scouts"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
                body = r.read()
                return body if raw else json.loads(body.decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(2)
    return None


def file_text(full, path, limit=20000):
    data = api("https://api.github.com/repos/%s/contents/%s" % (full, urllib.parse.quote(path)))
    if not data or data.get("encoding") != "base64":
        return ""
    try:
        return base64.b64decode(data.get("content") or "").decode("utf-8", "replace")[:limit]
    except Exception:
        return ""


def frontmatter(text):
    m = re.match(r"^﻿?---\s*\n(.*?)\n---", text or "", re.S)
    fm = {}
    for line in (m.group(1) if m else "").splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            fm[k.strip().lower()] = v.strip().strip("\"'")
    return fm


def demo(r):
    """Inspect one repo without running it. Returns (evidence kinds, checks, notes)."""
    full = r["full_name"]
    tree = api("https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (full, urllib.parse.quote(r.get("default_branch") or "HEAD")))
    paths = [t["path"] for t in (tree or {}).get("tree", []) if t.get("type") == "blob"]
    low = [p.lower() for p in paths]
    kinds, checks, notes = set(), {}, []

    skills = [p for p in paths if p.lower().endswith("skill.md")]
    if skills:
        fm = frontmatter(file_text(full, skills[0], 6000))
        ok = bool(fm.get("name")) and len(fm.get("description", "")) >= 20
        checks["skill_manifest"] = ok
        if ok:
            kinds.add("skill")
            notes.append("%d skill%s with a valid SKILL.md (e.g. %s)" % (len(skills), "" if len(skills) == 1 else "s", skills[0]))
        else:
            notes.append("SKILL.md found but its frontmatter lacks a name or a real description")

    manifest = next((p for p in paths if p.lower() in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")), None)
    if manifest:
        try:
            pj = json.loads(file_text(full, manifest, 50000) or "null")
            ok = isinstance(pj, dict) and bool(pj.get("name"))
        except ValueError:
            ok = False
        checks["plugin_manifest"] = ok
        if ok:
            kinds.add("plugin")
            notes.append("valid %s" % manifest)
        else:
            notes.append("%s is not valid JSON with a name" % manifest)

    deps = ""
    for name in ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml"):
        if name.lower() in low:
            deps += file_text(full, paths[low.index(name.lower())], 30000).lower() + "\n"
    if re.search(r"@modelcontextprotocol/sdk|\bfastmcp\b|\bmcp\[cli\]|[\"' ]mcp[\"'>=~ ]|mark3labs/mcp-go|modelcontextprotocol/go-sdk|\brmcp\b", deps):
        kinds.add("mcp")
        notes.append("depends on an MCP SDK")
    if re.search(r"claude-agent-sdk|@anthropic-ai/claude-agent-sdk|claude-code-sdk|@anthropic-ai/sdk|[\"' ]anthropic[\"'>=~ ]", deps):
        kinds.add("agent")
        notes.append("uses the Anthropic / Claude Agent SDK")

    readme = next((p for p in paths if p.lower() in ("readme.md", "readme.rst", "readme")), None)
    rlen = len(file_text(full, readme, 60000)) if readme else 0
    checks["readme"] = rlen >= 800
    checks["licence"] = bool(r.get("license")) or any(p.startswith(("license", "licence", "copying")) for p in low)
    pushed = r.get("pushed_at") or ""
    checks["active"] = pushed >= (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    checks["has_files"] = len(paths) >= 3
    return kinds, checks, notes, rlen


def score(r, kinds, checks, rlen):
    s = 40 if kinds else 0
    s += 15 if checks.get("readme") else 5 if rlen > 200 else 0
    s += 10 if checks.get("licence") else 0
    s += 15 if checks.get("active") else 0
    s += min(20, int(6 * math.log10((r.get("stargazers_count") or 0) + 1)))
    if any(v is False for k, v in checks.items() if k.endswith("_manifest")):
        s -= 15
    return max(0, min(100, s))


def main():
    now = datetime.now(timezone.utc)
    old = {}
    if os.path.exists(OUT):
        try:
            old = {c["full_name"].lower(): c for c in json.load(open(OUT)).get("candidates", [])}
        except Exception:
            old = {}
    since = (now - timedelta(days=21)).strftime("%Y-%m-%d")
    born = (now - timedelta(days=60)).strftime("%Y-%m-%d")   # scouts look for new work, not famous old repos
    report = []
    for scout, queries in SCOUTS.items():
        seen, picked = set(), []
        for q in queries:
            url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
                {"q": "%s stars:>=3 fork:false archived:false pushed:>=%s created:>=%s" % (q, since, born), "sort": "updated", "order": "desc", "per_page": 30})
            for r in (api(url) or {}).get("items", []):
                key = r["full_name"].lower()
                text = " ".join([r["full_name"], r.get("description") or "", " ".join(r.get("topics") or [])]).lower() + " "
                if key in seen or any(k in text for k in BLOCKED) or r["owner"]["login"] == "sample":
                    continue
                prev = old.get(key)
                if prev and prev.get("pushed_at") == r.get("pushed_at"):
                    continue  # nothing changed since the last demo
                seen.add(key)
                picked.append(r)
            time.sleep(2.5)
        picked.sort(key=lambda r: r.get("stargazers_count") or 0, reverse=True)
        for r in picked[:PER_SCOUT]:
            kinds, checks, notes, rlen = demo(r)
            rec = {
                "full_name": r["full_name"], "owner": r["owner"]["login"], "name": r["name"], "url": r["html_url"],
                "description": (r.get("description") or "")[:300], "stars": r.get("stargazers_count") or 0,
                "topics": (r.get("topics") or [])[:8], "license": (r.get("license") or {}).get("spdx_id"),
                "created_at": r.get("created_at"), "pushed_at": r.get("pushed_at"),
                "scout": scout, "kinds": sorted(kinds), "checks": checks, "notes": notes,
                "score": score(r, kinds, checks, rlen),
                "category": categorize({"name": r["name"], "description": r.get("description"), "topics": r.get("topics")}),
                "first_scouted": (old.get(r["full_name"].lower()) or {}).get("first_scouted") or now.isoformat(),
                "demoed_at": now.isoformat(),
            }
            old[r["full_name"].lower()] = rec
            report.append(rec)
            time.sleep(0.3)
        print("%s scout: demoed %d new or changed repos" % (scout, min(len(picked), PER_SCOUT)))

    cands = sorted(old.values(), key=lambda c: c.get("demoed_at") or "", reverse=True)[:KEEP]
    for c in sorted(report, key=lambda c: c["score"], reverse=True)[:15]:
        print("  %3d  %-45s %-8s %s" % (c["score"], c["full_name"], c["scout"], ", ".join(c["kinds"]) or "-"))
    if "--dry-run" in sys.argv:
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"updated": now.isoformat(), "demoed_this_run": len(report), "candidates": cands}, f, indent=1)


if __name__ == "__main__":
    main()
