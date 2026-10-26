#!/usr/bin/env python3
"""
Star Catcher - supervisor agent (runs daily in GitHub Actions).

Watches the other agents: the 6-hour data updater, the 12-hour health check,
the debug agent and the tests. It keeps one pinned "Status board" issue up to
date and flags any agent that has stopped running or keeps failing.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY (set by Actions).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
LABEL = "status"
TITLE = "Status board"

# workflow file -> (agent name, max hours between runs before it counts as stalled)
AGENTS = {
    "update.yml": ("Data updater (every 6h)", 8),
    "health.yml": ("Health check (every 12h)", 14),
    "test.yml": ("Tests (on every push)", None),
    "debug-agent.yml": ("Debug agent (on health/bug issues)", None),
}


def gh(path, method="GET", body=None):
    headers = {"User-Agent": "star-catcher-supervisor", "Accept": "application/vnd.github+json"}
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


def hours_since(ts):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 3600


def main():
    rows, problems = [], []
    for wf, (name, max_gap) in AGENTS.items():
        status, body = gh("/repos/%s/actions/workflows/%s/runs?per_page=5" % (REPO, wf))
        runs = (body or {}).get("workflow_runs", []) if status == 200 else []
        if not runs:
            rows.append("| %s | never ran | - | - |" % name)
            if max_gap:
                problems.append("%s has never run." % name)
            continue
        last = runs[0]
        concl = last.get("conclusion") or last.get("status")
        fails = sum(1 for r in runs if r.get("conclusion") == "failure")
        age = hours_since(last["created_at"])
        rows.append("| %s | %s | %.1fh ago | %d of last %d failed |" % (name, concl, age, fails, len(runs)))
        if max_gap and age > max_gap:
            problems.append("%s has not run for %.1f hours (expected every %d)." % (name, age, max_gap - 2))
        if fails >= 3:
            problems.append("%s failed %d of its last %d runs: %s" % (name, fails, len(runs), last.get("html_url")))

    _, health = gh("/repos/%s/issues?state=open&labels=health&per_page=5" % REPO)
    _, bugs = gh("/repos/%s/issues?state=open&labels=bug&per_page=10" % REPO)
    _, prs = gh("/repos/%s/pulls?state=open&per_page=10" % REPO)
    health, bugs, prs = health or [], bugs or [], prs or []
    for i in health:
        if hours_since(i["created_at"]) > 48:
            problems.append("Health issue #%d has been open for more than 2 days; the debug agent may be stuck." % i["number"])

    data_line = "unknown"
    try:
        with open(os.path.join(ROOT, "data", "repos.json")) as f:
            d = json.load(f)
        data_line = "%d repos · %d new and %d updated in the last scan · last scan %s" % (d.get("total", 0), d.get("new_this_run", 0), d.get("updated_this_run", 0), d.get("last_updated"))
    except Exception as e:
        problems.append("Could not read data/repos.json: %s" % e)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    verdict = "All agents healthy." if not problems else "Needs attention:\n" + "\n".join("- " + p for p in problems)
    body = "\n".join([
        "Updated by the supervisor agent at %s." % stamp, "", "**%s**" % ("OK" if not problems else "ATTENTION"), "", verdict, "",
        "### Agents", "| Agent | Last result | Last run | Recent failures |", "|---|---|---|---|", *rows, "",
        "### Data", data_line, "",
        "### Open work", "- Health issues: %s" % (", ".join("#%d" % i["number"] for i in health) or "none"),
        "- Bug issues: %s" % (", ".join("#%d" % i["number"] for i in bugs) or "none"),
        "- Open pull requests: %s" % (", ".join("#%d %s" % (p["number"], p["title"]) for p in prs) or "none"),
    ])
    print(body)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(body + "\n")
    if not (REPO and TOKEN):
        return
    gh("/repos/%s/labels" % REPO, "POST", {"name": LABEL, "color": "0e8a16", "description": "Status board kept by the supervisor agent"})
    _, existing = gh("/repos/%s/issues?state=open&labels=%s&per_page=1" % (REPO, LABEL))
    if existing:
        gh("/repos/%s/issues/%d" % (REPO, existing[0]["number"]), "PATCH", {"body": body, "title": TITLE + (" — attention needed" if problems else "")})
    else:
        gh("/repos/%s/issues" % REPO, "POST", {"title": TITLE, "body": body, "labels": [LABEL]})
    if problems and "--strict" in sys.argv:
        sys.exit(1)


if __name__ == "__main__":
    main()
