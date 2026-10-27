#!/usr/bin/env python3
"""
Star Catcher - senior agents (run daily, right after the scouts).

One senior agent per category reviews what the scouts demoed (data/scouted.json)
and approves at most a handful of "Verified picks" for its category. Each senior
has its own bar: the MCP senior only approves repos that really depend on an MCP
SDK, the skills & plugins senior needs a valid SKILL.md or plugin manifest, and
so on. Every approval comes with the reasons, and picks are re-reviewed each day,
so a repo that goes stale or breaks its manifest drops out.

Output: data/picks.json, rendered by build_pages.py as a "Verified picks" section
on each category page and a "Verified" pill on repo pages.
Flags: --dry-run prints decisions without writing.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOUTED = os.path.join(ROOT, "data", "scouted.json")
PICKS = os.path.join(ROOT, "data", "picks.json")
MAX_PICKS = 6


def has(c, *kinds):
    return any(k in c.get("kinds", []) for k in kinds)


# Seniors never vouch for these, even when the repo is listed: cheats, cracking, evasion and abuse tooling
# (keeps "Verified" trustworthy and the site safe for sponsors and ad networks).
NOT_VERIFIABLE = ("hack", "cheat", "crack", "exploit", "bypass", "jailbreak", "aimbot", "keylogger", "stealer", "phishing",
                  "spam", "bot farm", "account farm", "undetect", "evade", "evasion", "ddos", "malware", "ransom",
                  "anti-ban", "antiban", "avoid ban", "防封", "封号")
MAX_SKILLS = 300   # thousands of generated SKILL.md files look like a skill farm, not a curated pack


def basics(c):
    ch = c.get("checks", {})
    text = " ".join([c.get("full_name", ""), c.get("description", ""), " ".join(c.get("topics", []))]).lower()
    many = [int(n) for n in re.findall(r"^(\d+) skills? ", " ".join(c.get("notes", [])))]
    return (ch.get("readme") and ch.get("licence") and ch.get("has_files")
            and not any(v is False for k, v in ch.items() if k.endswith("_manifest"))
            and not any(w in text for w in NOT_VERIFIABLE)
            and not (many and many[0] > MAX_SKILLS))


# category -> (senior name, rule, minimum score, what the rule means)
SENIORS = {
    "MCP Servers": ("MCP senior", lambda c: has(c, "mcp"), 65, "depends on an MCP SDK"),
    "Skills & Plugins": ("Skills & plugins senior", lambda c: has(c, "skill", "plugin"), 65, "ships a valid SKILL.md or plugin manifest"),
    "Agents & SDK": ("Agents senior", lambda c: has(c, "agent", "mcp"), 65, "is built on the Anthropic / Claude Agent SDK or MCP"),
    "Dev Tools & CLI": ("Dev tools senior", lambda c: True, 70, "is an active, documented, licensed tool"),
    "Prompts & Guides": ("Guides senior", lambda c: True, 60, "is an active, documented, licensed guide"),
    "Apps & UIs": ("Apps senior", lambda c: True, 70, "is an active, documented, licensed app"),
}
def home(c):
    """Senior who reviews a candidate: proven evidence decides first, the repo's text second."""
    if has(c, "skill", "plugin") and not has(c, "mcp"):
        return "Skills & Plugins"
    if has(c, "mcp"):
        return "MCP Servers"
    if has(c, "agent"):
        return "Agents & SDK"
    return c.get("category") if c.get("category") in SENIORS else None


def main():
    now = datetime.now(timezone.utc).isoformat()
    try:
        cands = json.load(open(SCOUTED)).get("candidates", [])
    except (OSError, ValueError):
        print("no scouted.json yet; nothing to review")
        return
    prev = {}
    try:
        for cat, items in json.load(open(PICKS)).get("picks", {}).items():
            for p in items:
                prev[p["full_name"].lower()] = p
    except (OSError, ValueError):
        pass

    picks, log = {}, []
    for cat, (senior, rule, min_score, meaning) in SENIORS.items():
        pool = [c for c in cands if home(c) == cat]
        ok, rejected = [], 0
        for c in pool:
            if c.get("score", 0) >= min_score and basics(c) and rule(c):
                ok.append(c)
            else:
                rejected += 1
        ok.sort(key=lambda c: (c.get("score", 0), c.get("stars", 0)), reverse=True)
        chosen = []
        for c in ok[:MAX_PICKS]:
            was = prev.get(c["full_name"].lower())
            chosen.append({
                "full_name": c["full_name"], "owner": c["owner"], "name": c["name"], "url": c["url"],
                "description": c.get("description", ""), "stars": c.get("stars", 0), "score": c.get("score", 0),
                "senior": senior, "reason": "; ".join(["%s %s" % (c["name"], meaning)] + [n for n in c.get("notes", [])[:2] if n not in meaning]),
                "approved_at": (was or {}).get("approved_at") or now,
            })
        picks[cat] = chosen
        dropped = [p for p in prev.values() if p.get("senior") == senior and p["full_name"].lower() not in {x["full_name"].lower() for x in chosen}]
        log.append("%-24s reviewed %3d · approved %d · rejected %d · dropped %d" % (senior, len(pool), len(chosen), rejected, len(dropped)))
        for p in chosen:
            log.append("    ✓ %-45s score %3d  %s" % (p["full_name"], p["score"], p["reason"][:90]))

    print("\n".join(log))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Senior agents\n```\n%s\n```\n" % "\n".join(log))
    if "--dry-run" in sys.argv:
        return
    with open(PICKS, "w") as f:
        json.dump({"updated": now, "picks": picks}, f, indent=1)


if __name__ == "__main__":
    main()
