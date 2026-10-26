#!/usr/bin/env python3
"""
Star Catcher - health check agent (runs every 12 hours in GitHub Actions).

Checks the data file, the live site and the data workflow. If anything fails it
opens (or updates) one GitHub issue labelled "health"; when everything passes
again it closes that issue. The debug agent picks up "health" issues.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY (set by Actions), optional SITE_URL.
Run locally with --no-issue to only print the report.
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
MAX_DATA_AGE_HOURS = 8          # data refreshes every 6 hours; allow slack
MIN_REPOS = 50
LABEL = "health"
TITLE = "Health check failing"


def http(url, method="GET", body=None, gh=False):
    headers = {"User-Agent": "star-catcher-health"}
    if gh:
        headers["Accept"] = "application/vnd.github+json"
        if TOKEN:
            headers["Authorization"] = "Bearer " + TOKEN
    data = json.dumps(body).encode() if body is not None else None
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # network errors
        return 0, str(e).encode()


def gh_api(path, method="GET", body=None):
    status, raw = http("https://api.github.com" + path, method, body, gh=True)
    try:
        return status, json.loads(raw or b"null")
    except ValueError:
        return status, None


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    if "/" in REPO:
        owner, name = REPO.split("/", 1)
        if name.lower() == owner.lower() + ".github.io":
            return "https://%s.github.io/" % owner.lower()
        return "https://%s.github.io/%s/" % (owner.lower(), name)
    return ""


def check_data(results):
    path = os.path.join(ROOT, "data", "repos.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        results.append(("Data file loads", False, "data/repos.json could not be read: %s" % e))
        return
    repos = data.get("repos", [])
    results.append(("Data file loads", True, "%d repos" % len(repos)))
    results.append(("Real data, not the sample", not data.get("sample"), "sample flag is set: run the 'Update repo data' workflow" if data.get("sample") else "ok"))
    results.append(("Enough repos", len(repos) >= MIN_REPOS, "%d repos (minimum %d)" % (len(repos), MIN_REPOS)))
    ts = data.get("last_updated")
    if ts:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 3600
        results.append(("Data is fresh", age <= MAX_DATA_AGE_HOURS, "last scan %.1f hours ago (limit %d)" % (age, MAX_DATA_AGE_HOURS)))
    else:
        results.append(("Data is fresh", False, "last_updated is missing"))
    required = ["id", "name", "full_name", "url", "stars", "category"]
    bad = [r.get("full_name", "?") for r in repos[:200] if any(k not in r for k in required)]
    results.append(("Repo records complete", not bad, "missing fields in: " + ", ".join(bad[:5]) if bad else "ok"))
    ids = [r.get("id") for r in repos]
    results.append(("No duplicate repos", len(ids) == len(set(ids)), "%d duplicates" % (len(ids) - len(set(ids)))))


def check_site(results):
    url = site_url()
    if not url:
        results.append(("Site reachable", False, "SITE_URL not set and repo unknown"))
        return
    status, raw = http(url)
    ok = status == 200 and b"Star Catcher" in (raw or b"")
    results.append(("Site reachable", ok, "%s returned %s" % (url, status)))
    status, _ = http(url + "data/repos.json")
    results.append(("Site serves data", status == 200, "%sdata/repos.json returned %s" % (url, status)))


def check_workflow(results):
    if not REPO:
        return
    status, body = gh_api("/repos/%s/actions/workflows/update.yml/runs?per_page=3" % REPO)
    runs = (body or {}).get("workflow_runs", []) if status == 200 else []
    if not runs:
        results.append(("Data workflow ran", False, "no runs found (status %s)" % status))
        return
    last = runs[0]
    ok = last.get("conclusion") in ("success", None) and last.get("status") != "failure"
    results.append(("Data workflow succeeded", ok, "last run: %s (%s) %s" % (last.get("conclusion") or last.get("status"), last.get("created_at"), last.get("html_url"))))


def report(results):
    lines = ["| Check | Result | Detail |", "|---|---|---|"]
    for name, ok, detail in results:
        lines.append("| %s | %s | %s |" % (name, "pass" if ok else "**FAIL**", str(detail).replace("|", "/")))
    return "\n".join(lines)


def sync_issue(results, md):
    failing = [r for r in results if not r[1]]
    status, issues = gh_api("/repos/%s/issues?state=open&labels=%s&per_page=10" % (REPO, LABEL))
    open_issue = (issues or [None])[0] if status == 200 and issues else None
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if failing:
        gh_api("/repos/%s/labels" % REPO, "POST", {"name": LABEL, "color": "d93f0b", "description": "Opened by the health check agent"})
        body = "The 12-hour health check found %d problem(s) at %s.\n\n%s\n\nThe debug agent will look at this issue. Close it only when the next health check passes." % (len(failing), stamp, md)
        if open_issue:
            gh_api("/repos/%s/issues/%s/comments" % (REPO, open_issue["number"]), "POST", {"body": body})
        else:
            gh_api("/repos/%s/issues" % REPO, "POST", {"title": TITLE, "body": body, "labels": [LABEL]})
    elif open_issue:
        gh_api("/repos/%s/issues/%s/comments" % (REPO, open_issue["number"]), "POST", {"body": "All checks pass again at %s. Closing.\n\n%s" % (stamp, md)})
        gh_api("/repos/%s/issues/%s" % (REPO, open_issue["number"]), "PATCH", {"state": "closed"})


def main():
    results = []
    check_data(results)
    check_site(results)
    check_workflow(results)
    md = report(results)
    print(md)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("## Star Catcher health\n\n" + md + "\n")
    if "--no-issue" not in sys.argv and REPO and TOKEN:
        sync_issue(results, md)
    failing = [r for r in results if not r[1]]
    sys.exit(1 if failing else 0)


if __name__ == "__main__":
    main()
