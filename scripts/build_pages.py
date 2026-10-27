#!/usr/bin/env python3
"""
Star Catcher - growth pages builder (runs after every data scan).

Turns data/repos.json into pages search engines can index and people can share:
  r/<owner>/<repo>/          one page per repo (title, description, stats, related repos, badge)
  c/<category>/              "Best <category> for Claude" top lists
  new/                       repos discovered this week
  advertise/                 sponsor page with live audience numbers (links to the sponsor request form)
  t/<topic>/                 "Best <topic> repos for Claude" pages for every topic shared by enough repos
  trending/                  fastest-growing repos this week (from data/history.json)
  badge/<owner>/<repo>/trending.svg  "#N trending in <region>" badge (falls back to the rank badge)
  mcp/                       install page for the Star Catcher MCP server (mcp/server.mjs)
  badge/<owner>/<repo>.svg   a README badge repo owners can add (backlinks)
  sitemap.xml, robots.txt, feed.xml (RSS of new repos)

Output is static HTML that matches the site's look. No dependencies.
Env: SITE_URL (optional; defaults to the GitHub Pages address of GITHUB_REPOSITORY).
"""
import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "repos.json")
SAFE = re.compile(r"^[A-Za-z0-9._-]+$")

CATS = [
    ("MCP Servers", "mcp-servers", "MCP Nebula", "#4DA8FF", "MCP servers that give Claude new tools and data sources: databases, browsers, design tools, APIs and more."),
    ("Agents & SDK", "agents-sdk", "Agent Cluster", "#A77BFF", "Agents, subagents and SDKs for building with Claude and the Claude Agent SDK."),
    ("Skills & Plugins", "skills-plugins", "Skills Belt", "#FF8A3D", "Claude Code skills, plugins, slash commands and hooks you can install."),
    ("Dev Tools & CLI", "dev-tools-cli", "Tools System", "#3DE0C0", "Command-line tools, routers, usage trackers and other developer tools around Claude Code."),
    ("Prompts & Guides", "prompts-guides", "Guide Station", "#FF5FA2", "Guides, prompt collections, CLAUDE.md examples, courses and awesome lists."),
    ("Apps & UIs", "apps-uis", "App Colony", "#FFD23F", "Desktop apps, chat UIs, editor extensions and web interfaces for Claude."),
    ("Other", "other", "Outer Rim", "#9BE15D", "Everything else that mentions Claude, Anthropic or MCP."),
]
CAT = {c[0]: c for c in CATS}


def site_url():
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "pahadiji/star-catcher")
    owner, name = repo.split("/", 1)
    if name.lower() == owner.lower() + ".github.io":
        return "https://%s.github.io/" % owner.lower()
    return "https://%s.github.io/%s/" % (owner.lower(), name)


def fmt(n):
    n = n or 0
    if n >= 10000:
        return "%dk" % round(n / 1000)
    if n >= 1000:
        return "%.1fk" % (n / 1000)
    return str(n)


def rank(n, th):
    return "Legendary" if n >= th["L"] else "Epic" if n >= th["E"] else "Rare" if n >= th["R"] else "Common"


def stage(n):
    return "Giant" if n >= 10000 else "Star" if n >= 1000 else "Protostar"


E = html.escape


def page(title, desc, canonical, body, extra_head=""):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{c}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{c}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#07070F">
<link rel="alternate" type="application/rss+xml" title="New Claude repos" href="{base}feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}assets/page.css">
{x}
</head>
<body>
<header class="bar"><a class="brand" href="{base}">✳ Star Catcher</a><nav><a href="{base}c/mcp-servers/">MCP</a><a href="{base}c/skills-plugins/">Skills</a><a href="{base}c/agents-sdk/">Agents</a><a href="{base}new/">New</a><a href="{base}trending/">Trending</a><a href="{base}mcp/">MCP server</a><a class="go" href="{base}">Open the galaxy</a></nav></header>
<main>
{b}
</main>
<footer>Data from the GitHub API, refreshed every 6 hours. Not affiliated with Anthropic or GitHub. <a href="{base}feed.xml">RSS</a> · <a href="{base}advertise/">Advertise</a></footer>
</body>
</html>
""".format(t=E(title), d=E(desc), c=E(canonical), b=body, x=extra_head, base=BASE)


def repo_card(r, th, prefix):
    return '<li><a href="{p}r/{o}/{n}/"><b>{name}</b> <span>by {o}</span></a><p>{d}</p><small>★ {s} · {rk} · {lang}</small></li>'.format(
        p=prefix, o=E(r["owner"]), n=E(r["name"]), name=E(r["name"]), d=E((r.get("description") or "")[:160]),
        s=fmt(r.get("stars")), rk=rank(r.get("stars") or 0, th), lang=E(r.get("language") or "—"))


def picks_html(items, tracked):
    """'Verified picks' block: new repos the scouts demoed and this category's senior agent approved."""
    if not items:
        return ""
    li = []
    for p in items:
        href = "%sr/%s/%s/" % (BASE, p["owner"], p["name"]) if p["full_name"].lower() in tracked else p["url"]
        li.append('<li><a href="{h}"><b>{n}</b> <span>by {o}</span></a><p>{d}</p><small>✓ {why}</small></li>'.format(
            h=E(href), n=E(p["name"]), o=E(p["owner"]), d=E((p.get("description") or "")[:160]), why=E(p["reason"][:180])))
    return ('<section><h2>✓ Verified picks</h2><p class="lede">New repos our scouts tried and the %s approved. '
            'Checked daily: the manifest is valid, the README is real, it has a licence and it is active.</p><ul class="list">%s</ul></section>\n'
            % (E(items[0]["senior"]), "".join(li)))


TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
TOPIC_MIN = 8       # repos needed before a topic gets its own page
TOPIC_MAX = 300     # topic pages built (most popular first)
TREND_TOP = 50      # repos per region that can carry a "#N trending" badge


def gains(repos, history, now):
    """Stars gained over the last ~7 days per repo. Until a week of history exists,
    young repos are estimated from their stars per day since creation."""
    out = {}
    for r in repos:
        pts = history.get(str(r["id"])) or []
        if len(pts) >= 2:
            days = max(1, (datetime.fromisoformat(pts[-1][0]) - datetime.fromisoformat(pts[0][0])).days)
            out[r["full_name"]] = round((pts[-1][1] - pts[0][1]) * 7 / days)
        else:
            try:
                age = (now - datetime.fromisoformat((r.get("created_at") or "").replace("Z", "+00:00"))).days
            except ValueError:
                age = 9999
            out[r["full_name"]] = round((r.get("stars") or 0) * 7 / max(age, 7)) if age <= 60 else 0
    return out


def cat_topics(items, topics):
    count = {}
    for r in items:
        for t in r.get("topics") or []:
            if t in topics:
                count[t] = count.get(t, 0) + 1
    top = sorted(count, key=lambda t: -count[t])[:16]
    if not top:
        return ""
    return '<section><h2>Popular topics</h2><ul class="pills">%s</ul></section>\n' % "".join(
        '<li><a href="%st/%s/">%s · %d</a></li>' % (BASE, t, E(t), count[t]) for t in top)


def badge_svg(r, th, value=None):
    label, value = "star catcher", value or "%s · %s" % (rank(r.get("stars") or 0, th), CAT.get(r.get("category"), CATS[-1])[2])
    lw, vw = 82, 10 + 7 * len(value)
    color = CAT.get(r.get("category"), CATS[-1])[3]
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{l}: {v}">'
            '<rect width="{lw}" height="20" fill="#12121F"/><rect x="{lw}" width="{vw}" height="20" fill="{c}"/>'
            '<g font-family="Verdana,DejaVu Sans,sans-serif" font-size="11"><text x="8" y="14" fill="#C6FF3D">✳ {l}</text>'
            '<text x="{tx}" y="14" fill="#07070F">{v}</text></g></svg>').format(w=lw + vw, lw=lw, vw=vw, c=color, l=E(label), v=E(value), tx=lw + 6)


def main():
    global BASE
    BASE = site_url()
    with open(DATA) as f:
        data = json.load(f)
    repos = [r for r in data.get("repos", []) if SAFE.match(str(r.get("owner", ""))) and SAFE.match(str(r.get("name", "")))
             and int(r.get("id") or 0) >= 100000]   # skip leftover demo records (ids 1000-1017)
    repos.sort(key=lambda r: r.get("stars") or 0, reverse=True)
    if not repos:
        print("no repos; nothing to build")
        return
    # Verified picks from the senior agents (scripts/seniors.py), if they have run.
    try:
        with open(os.path.join(ROOT, "data", "picks.json")) as f:
            picks = json.load(f).get("picks", {})
    except (OSError, ValueError):
        picks = {}
    verified = {p["full_name"].lower(): p for items in picks.values() for p in items}
    tracked = {r["full_name"].lower() for r in repos}
    at = lambda p: repos[min(len(repos) - 1, int(len(repos) * p))].get("stars") or 0
    th = {"L": max(10, at(0.02)), "E": max(5, at(0.10)), "R": max(2, at(0.35))}
    now = datetime.now(timezone.utc)
    week = (now - timedelta(days=14)).isoformat()   # "new" = created on GitHub in the last 14 days
    updated = now.strftime("%d %b %Y")

    # Trending: stars gained this week, ranked inside each region.
    try:
        with open(os.path.join(ROOT, "data", "history.json")) as f:
            history = json.load(f)
    except (OSError, ValueError):
        history = {}
    gain = gains(repos, history, now)
    trend = {}
    for key in CAT:
        ranked = sorted([r for r in repos if (r.get("category") if r.get("category") in CAT else "Other") == key and gain.get(r["full_name"], 0) > 0],
                        key=lambda r: gain[r["full_name"]], reverse=True)[:TREND_TOP]
        for i, r in enumerate(ranked, 1):
            trend[r["full_name"]] = (i, CAT[key][2])

    # Topics with enough repos get their own page.
    topic_count = {}
    for r in repos:
        for t in set(r.get("topics") or []):
            if TOPIC_RE.match(t):
                topic_count[t] = topic_count.get(t, 0) + 1
    topics = dict(sorted([(t, c) for t, c in topic_count.items() if c >= TOPIC_MIN], key=lambda x: -x[1])[:TOPIC_MAX])
    topic_link = lambda t: ('<li><a href="%st/%s/">%s</a></li>' % (BASE, t, E(t))) if t in topics else "<li>%s</li>" % E(t)

    for d in ("r", "c", "t", "new", "trending", "badge"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)

    by_cat = {}
    for r in repos:
        by_cat.setdefault(r.get("category") if r.get("category") in CAT else "Other", []).append(r)

    urls = [(BASE, now.date().isoformat())]
    # Repo pages + badges
    for r in repos:
        o, n = r["owner"], r["name"]
        cat = CAT.get(r.get("category"), CATS[-1])
        rk = rank(r.get("stars") or 0, th)
        related = [x for x in by_cat.get(cat[0], []) if x is not r][:8]
        canonical = "%sr/%s/%s/" % (BASE, o, n)
        desc = (r.get("description") or "%s by %s" % (n, o)).strip()
        title = "%s by %s — %s for Claude | Star Catcher" % (n, o, cat[0].split(" &")[0].rstrip("s") if cat[0] != "Other" else "Project")
        badge_md = "[![Star Catcher](%sbadge/%s/%s.svg)](%s)" % (BASE, o, n, canonical)
        ld = json.dumps({"@context": "https://schema.org", "@type": "SoftwareSourceCode", "name": n, "author": {"@type": "Person", "name": o},
                         "codeRepository": r.get("url"), "description": desc, "programmingLanguage": r.get("language") or None,
                         "license": r.get("license") or None, "keywords": ", ".join(r.get("topics") or [])})
        body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › <a href="{base}c/{slug}/">{label}</a> › {n}</nav>
<article class="repo" style="--c:{color}">
  <div class="head"><span class="orb" aria-hidden="true"></span><div><h1>{n}</h1><p class="by">by {o}</p></div></div>
  <p class="desc">{desc}</p>
  <ul class="pills"><li class="type">{label}</li>{ver}<li>{rk}</li><li>{stg}</li>{topics}</ul>
  <dl class="stats"><div><dt>Stars</dt><dd>★ {stars}</dd></div><div><dt>Forks</dt><dd>{forks}</dd></div><div><dt>Language</dt><dd>{lang}</dd></div><div><dt>Last push</dt><dd>{push}</dd></div></dl>
  <div class="actions"><a class="btn go" href="{base}?star={o}/{n}">Find it in the galaxy</a><a class="btn" href="{url}" rel="noopener">Open on GitHub</a></div>
  <pre class="install"><code>git clone {url}.git</code></pre>
</article>
<section><h2>More in {label}</h2><ul class="list">{related}</ul><p><a href="{base}c/{slug}/">See the full {label} list</a></p></section>
<section class="owner"><h2>Is this your repo?</h2><p>Add this badge to your README so visitors can find it in the galaxy:</p><img src="{base}badge/{o}/{n}.svg" alt="Star Catcher badge"><pre><code>{badge}</code></pre>
<p>Or the trending badge. It shows your weekly rank while you are in the top {top} of {label}, and your usual badge otherwise:</p><img src="{base}badge/{o}/{n}/trending.svg" alt="Star Catcher trending badge"><pre><code>{tbadge}</code></pre></section>
""".format(base=BASE, slug=cat[1], label=E(cat[2]), n=E(n), o=E(o), color=cat[3], desc=E(desc), rk=rk, stg=stage(r.get("stars") or 0),
           topics="".join(topic_link(t) for t in (r.get("topics") or [])[:5]), stars=fmt(r.get("stars")), forks=fmt(r.get("forks")),
           lang=E(r.get("language") or "—"), push=E((r.get("pushed_at") or "")[:10]), url=E(r.get("url") or "#"),
           related="".join(repo_card(x, th, BASE) for x in related), badge=E(badge_md), top=TREND_TOP,
           tbadge=E("[![Star Catcher trending](%sbadge/%s/%s/trending.svg)](%s)" % (BASE, o, n, canonical)),
           ver=('<li title="%s">✓ Verified by the %s</li>' % (E(verified[r["full_name"].lower()]["reason"]), E(verified[r["full_name"].lower()]["senior"]))) if r["full_name"].lower() in verified else "")
        out = os.path.join(ROOT, "r", o, n)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w") as f:
            f.write(page(title, desc[:155], canonical, body, '<script type="application/ld+json">%s</script>' % ld.replace("</", "<\\/")))
        os.makedirs(os.path.join(ROOT, "badge", o), exist_ok=True)
        with open(os.path.join(ROOT, "badge", o, n + ".svg"), "w") as f:
            f.write(badge_svg(r, th))
        os.makedirs(os.path.join(ROOT, "badge", o, n), exist_ok=True)
        tr = trend.get(r["full_name"])
        with open(os.path.join(ROOT, "badge", o, n, "trending.svg"), "w") as f:
            f.write(badge_svg(r, th, ("#%d trending · %s" % tr) if tr else None))
        urls.append((canonical, (r.get("pushed_at") or now.isoformat())[:10]))

    # Category pages
    for key, slug, label, color, blurb in CATS:
        items = by_cat.get(key, [])
        if not items:
            continue
        canonical = "%sc/%s/" % (BASE, slug)
        title = "Best %s for Claude (%d repos, updated %s) | Star Catcher" % (key, len(items), updated)
        body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › {label}</nav>
<h1 style="color:{color}">Best {key} for Claude</h1>
<p class="lede">{blurb} {count} repos, ranked by GitHub stars and refreshed every 6 hours. Last update: {updated}.</p>
<p><a class="btn go" href="{base}">Explore {label} in the galaxy</a></p>
{picks}{ctopics}<ol class="list ranked">{items}</ol>
""".format(ctopics=cat_topics(items, topics),base=BASE, label=E(label), color=color, key=E(key), blurb=E(blurb), count=len(items), updated=updated,
           items="".join(repo_card(x, th, BASE) for x in items[:150]), picks=picks_html(picks.get(key, []), tracked))
        os.makedirs(os.path.join(ROOT, "c", slug), exist_ok=True)
        with open(os.path.join(ROOT, "c", slug, "index.html"), "w") as f:
            f.write(page(title, "%s %d repos ranked by stars, updated every 6 hours." % (blurb, len(items)), canonical, body))
        urls.append((canonical, now.date().isoformat()))

    # New this week + RSS
    fresh = sorted([r for r in repos if (r.get("created_at") or "") >= week], key=lambda r: r.get("created_at") or "", reverse=True)
    canonical = BASE + "new/"
    body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › New this week</nav>
<h1>New Claude repos</h1>
<p class="lede">{n} repos were created in the last 14 days. New ones are added every 6 hours. <a href="{base}feed.xml">Subscribe via RSS</a>.</p>
<ul class="list">{items}</ul>
""".format(base=BASE, n=len(fresh), items="".join(repo_card(x, th, BASE) for x in fresh[:200]) or "<li>No new repos yet this week.</li>")
    os.makedirs(os.path.join(ROOT, "new"), exist_ok=True)
    with open(os.path.join(ROOT, "new", "index.html"), "w") as f:
        f.write(page("New Claude, Claude Code and MCP repos | Star Catcher", "%d Claude, MCP and agent repos created in the last 14 days." % len(fresh), canonical, body))
    urls.append((canonical, now.date().isoformat()))

    # Topic pages
    for t, cnt in topics.items():
        items = [r for r in repos if t in (r.get("topics") or [])]
        nice = t.replace("-", " ")
        canonical = "%st/%s/" % (BASE, t)
        related = sorted({x for r in items for x in (r.get("topics") or []) if x in topics and x != t},
                         key=lambda x: -sum(1 for r in items if x in (r.get("topics") or [])))[:12]
        body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › Topics › {t}</nav>
<h1>Best {nice} repos for Claude</h1>
<p class="lede">{n} Claude, Claude Code, MCP and agent repos tagged <b>{t}</b> on GitHub, ranked by stars and refreshed every 6 hours. Last update: {updated}.</p>
{rel}<ol class="list ranked">{items}</ol>
""".format(base=BASE, t=E(t), nice=E(nice), n=cnt, updated=updated,
           rel=('<section><h2>Related topics</h2><ul class="pills">%s</ul></section>' % "".join(topic_link(x) for x in related)) if related else "",
           items="".join(repo_card(x, th, BASE) for x in items[:150]))
        os.makedirs(os.path.join(ROOT, "t", t), exist_ok=True)
        with open(os.path.join(ROOT, "t", t, "index.html"), "w") as f:
            f.write(page("Best %s repos for Claude (%d, updated %s) | Star Catcher" % (nice, cnt, updated),
                         "%d %s repos for Claude, Claude Code and MCP, ranked by GitHub stars and updated every 6 hours." % (cnt, nice), canonical, body))
        urls.append((canonical, now.date().isoformat()))

    # Trending this week
    hot = sorted([r for r in repos if gain.get(r["full_name"], 0) > 0], key=lambda r: gain[r["full_name"]], reverse=True)[:100]
    canonical = BASE + "trending/"
    body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › Trending</nav>
<h1>Trending Claude repos this week</h1>
<p class="lede">The Claude, Claude Code, MCP and agent repos that gained the most GitHub stars in the last 7 days. Updated every 6 hours. Repo owners: show your rank with the trending badge on your repo's page.</p>
<ol class="list ranked">{items}</ol>
""".format(base=BASE, items="".join(repo_card(x, th, BASE).replace("<small>", "<small>+%s★ this week · " % fmt(gain[x["full_name"]]), 1) for x in hot)
           or "<li>Not enough data yet; check back tomorrow.</li>")
    os.makedirs(os.path.join(ROOT, "trending"), exist_ok=True)
    with open(os.path.join(ROOT, "trending", "index.html"), "w") as f:
        f.write(page("Trending Claude, Claude Code and MCP repos this week | Star Catcher", "The Claude and MCP repos gaining the most GitHub stars this week.", canonical, body))
    urls.append((canonical, now.date().isoformat()))

    # MCP server install page (the server itself is mcp/server.mjs, served as a static file)
    canonical = BASE + "mcp/"
    body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › MCP server</nav>
<h1>Ask Claude about every Claude repo</h1>
<p class="lede">The Star Catcher MCP server lets Claude search all {n} repos on this site: find a skill or MCP server for a job, see what is trending, read verified picks. It is one small file with no dependencies (Node 18+), and it only reads this site's public data.</p>
<section><h2>Claude Code</h2><pre><code>curl -fsSL {base}mcp/server.mjs -o ~/.star-catcher-mcp.mjs
claude mcp add star-catcher -- node ~/.star-catcher-mcp.mjs</code></pre></section>
<section><h2>Claude Desktop</h2><p>Download <a href="{base}mcp/server.mjs">server.mjs</a>, then add this to <code>claude_desktop_config.json</code>:</p>
<pre><code>{{"mcpServers": {{"star-catcher": {{"command": "node", "args": ["/path/to/server.mjs"]}}}}}}</code></pre></section>
<section><h2>Tools</h2><ul class="list">
<li><b>search_repos</b><p>Find repos by keyword, optionally in one category.</p></li>
<li><b>trending</b><p>Fastest-growing repos this week.</p></li>
<li><b>repo_info</b><p>Details for one repo, with its Star Catcher page.</p></li>
<li><b>verified_picks</b><p>New repos approved by the senior agents.</p></li>
<li><b>list_topics</b><p>Popular topics and how many repos each has.</p></li>
</ul></section>
<p>Try: <i>"Use star-catcher to find an MCP server for Postgres"</i> or <i>"What Claude Code skills are trending this week?"</i></p>
""".format(base=BASE, n=len(repos))
    os.makedirs(os.path.join(ROOT, "mcp"), exist_ok=True)
    with open(os.path.join(ROOT, "mcp", "index.html"), "w") as f:
        f.write(page("Star Catcher MCP server: let Claude search every Claude and MCP repo", "Install the Star Catcher MCP server so Claude can search %d Claude, MCP and agent repos." % len(repos), canonical, body))
    urls.append((canonical, now.date().isoformat()))
    with open(os.path.join(ROOT, "data", "trending.json"), "w") as f:
        json.dump([{"full_name": r["full_name"], "gain": gain[r["full_name"]], "category": r.get("category")} for r in hot], f, separators=(",", ":"))
    with open(os.path.join(ROOT, "data", "topics.json"), "w") as f:
        json.dump(topics, f, separators=(",", ":"))

    # Advertise page: live numbers sponsors ask for, and one way to get in touch (a GitHub issue form).
    repo_slug = os.environ.get("GITHUB_REPOSITORY", "pahadiji/star-catcher")
    form = "https://github.com/%s/issues/new?template=sponsor.yml" % repo_slug
    total_stars = sum(r.get("stars") or 0 for r in repos)
    cat_rows = "".join("<li><a href=\"{b}c/{s}/\"><b>{k}</b></a> <span>{n} repos</span></li>".format(b=BASE, s=c[1], k=E(c[0]), n=len(by_cat.get(c[0], [])))
                       for c in CATS if by_cat.get(c[0]))
    body = """
<nav class="crumbs"><a href="{base}">Galaxy</a> › Advertise</nav>
<h1>Put your AI developer tool in front of Claude builders</h1>
<p class="lede">Star Catcher maps every Claude, Claude Code, MCP, skill and agent repo on GitHub. The people who browse it are developers choosing tools for Claude right now.</p>
<dl class="stats"><div><dt>Repos tracked</dt><dd>{total}</dd></div><div><dt>Combined GitHub stars</dt><dd>★ {stars}</dd></div><div><dt>New in 14 days</dt><dd>{fresh}</dd></div><div><dt>Refresh</dt><dd>every 6 hours</dd></div></dl>
<section><h2>Placements</h2><ul class="list">
<li><b>Sponsored star</b><p>A golden star in the centre of the galaxy plus a sponsor card in the side panel. One sponsor at a time, clearly labelled, links use rel="sponsored".</p></li>
<li><b>Weekly new-repos roundup</b><p>A labelled mention in the weekly roundup of new Claude repos that goes out on social media.</p></li>
</ul></section>
<section><h2>Audience by category</h2><ul class="list">{cats}</ul></section>
<p><a class="btn go" href="{form}" rel="noopener">Request a placement</a></p>
<p><small>Requests are handled through a short form on GitHub. We only accept tools that are useful to developers, and we never sell a ranking.</small></p>
""".format(base=BASE, total=len(repos), stars=("%.1fM" % (total_stars / 1e6)) if total_stars >= 1e6 else fmt(total_stars), fresh=len(fresh), cats=cat_rows, form=E(form))
    canonical = BASE + "advertise/"
    os.makedirs(os.path.join(ROOT, "advertise"), exist_ok=True)
    with open(os.path.join(ROOT, "advertise", "index.html"), "w") as f:
        f.write(page("Advertise on Star Catcher: reach developers building with Claude", "Sponsor placements on Star Catcher, the map of %d Claude, MCP and agent repos." % len(repos), canonical, body))
    urls.append((canonical, now.date().isoformat()))

    items = "".join(
        "<item><title>{t}</title><link>{l}</link><guid>{l}</guid><pubDate>{d}</pubDate><description>{s}</description></item>".format(
            t=E("%s by %s (★%s)" % (r["name"], r["owner"], fmt(r.get("stars")))), l=E("%sr/%s/%s/" % (BASE, r["owner"], r["name"])),
            d=datetime.fromisoformat((r.get("created_at") or now.isoformat()).replace("Z", "+00:00")).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            s=E(r.get("description") or ""))
        for r in fresh[:50])
    with open(os.path.join(ROOT, "feed.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Star Catcher: new Claude repos</title>'
                '<link>%s</link><description>New Claude, Claude Code and MCP repos, found every 6 hours.</description>%s</channel></rss>' % (E(BASE), items))

    with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u, d in urls:
            f.write("<url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (E(u), d))
        f.write("</urlset>\n")
    with open(os.path.join(ROOT, "robots.txt"), "w") as f:
        f.write("User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % BASE)
    print("built %d repo pages, %d category pages, %d new this week, sitemap with %d urls" % (len(repos), len(by_cat), len(fresh), len(urls)))


if __name__ == "__main__":
    main()
