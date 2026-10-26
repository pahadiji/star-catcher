#!/usr/bin/env python3
"""
Star Catcher - growth pages builder (runs after every data scan).

Turns data/repos.json into pages search engines can index and people can share:
  r/<owner>/<repo>/          one page per repo (title, description, stats, related repos, badge)
  c/<category>/              "Best <category> for Claude" top lists
  new/                       repos discovered this week
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
<header class="bar"><a class="brand" href="{base}">✳ Star Catcher</a><nav><a href="{base}c/mcp-servers/">MCP</a><a href="{base}c/skills-plugins/">Skills</a><a href="{base}c/agents-sdk/">Agents</a><a href="{base}new/">New</a><a class="go" href="{base}">Open the galaxy</a></nav></header>
<main>
{b}
</main>
<footer>Data from the GitHub API, refreshed every 6 hours. Not affiliated with Anthropic or GitHub. <a href="{base}feed.xml">RSS</a></footer>
</body>
</html>
""".format(t=E(title), d=E(desc), c=E(canonical), b=body, x=extra_head, base=BASE)


def repo_card(r, th, prefix):
    return '<li><a href="{p}r/{o}/{n}/"><b>{name}</b> <span>by {o}</span></a><p>{d}</p><small>★ {s} · {rk} · {lang}</small></li>'.format(
        p=prefix, o=E(r["owner"]), n=E(r["name"]), name=E(r["name"]), d=E((r.get("description") or "")[:160]),
        s=fmt(r.get("stars")), rk=rank(r.get("stars") or 0, th), lang=E(r.get("language") or "—"))


def badge_svg(r, th):
    label, value = "star catcher", "%s · %s" % (rank(r.get("stars") or 0, th), CAT.get(r.get("category"), CATS[-1])[2])
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
    repos = [r for r in data.get("repos", []) if SAFE.match(str(r.get("owner", ""))) and SAFE.match(str(r.get("name", "")))]
    repos.sort(key=lambda r: r.get("stars") or 0, reverse=True)
    if not repos:
        print("no repos; nothing to build")
        return
    at = lambda p: repos[min(len(repos) - 1, int(len(repos) * p))].get("stars") or 0
    th = {"L": max(10, at(0.02)), "E": max(5, at(0.10)), "R": max(2, at(0.35))}
    now = datetime.now(timezone.utc)
    week = (now - timedelta(days=14)).isoformat()   # "new" = created on GitHub in the last 14 days
    updated = now.strftime("%d %b %Y")

    for d in ("r", "c", "new", "badge"):
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
  <ul class="pills"><li class="type">{label}</li><li>{rk}</li><li>{stg}</li>{topics}</ul>
  <dl class="stats"><div><dt>Stars</dt><dd>★ {stars}</dd></div><div><dt>Forks</dt><dd>{forks}</dd></div><div><dt>Language</dt><dd>{lang}</dd></div><div><dt>Last push</dt><dd>{push}</dd></div></dl>
  <div class="actions"><a class="btn go" href="{base}?star={o}/{n}">Find it in the galaxy</a><a class="btn" href="{url}" rel="noopener">Open on GitHub</a></div>
  <pre class="install"><code>git clone {url}.git</code></pre>
</article>
<section><h2>More in {label}</h2><ul class="list">{related}</ul><p><a href="{base}c/{slug}/">See the full {label} list</a></p></section>
<section class="owner"><h2>Is this your repo?</h2><p>Add this badge to your README so visitors can find it in the galaxy:</p><img src="{base}badge/{o}/{n}.svg" alt="Star Catcher badge"><pre><code>{badge}</code></pre></section>
""".format(base=BASE, slug=cat[1], label=E(cat[2]), n=E(n), o=E(o), color=cat[3], desc=E(desc), rk=rk, stg=stage(r.get("stars") or 0),
           topics="".join("<li>%s</li>" % E(t) for t in (r.get("topics") or [])[:5]), stars=fmt(r.get("stars")), forks=fmt(r.get("forks")),
           lang=E(r.get("language") or "—"), push=E((r.get("pushed_at") or "")[:10]), url=E(r.get("url") or "#"),
           related="".join(repo_card(x, th, BASE) for x in related), badge=E(badge_md))
        out = os.path.join(ROOT, "r", o, n)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w") as f:
            f.write(page(title, desc[:155], canonical, body, '<script type="application/ld+json">%s</script>' % ld.replace("</", "<\\/")))
        os.makedirs(os.path.join(ROOT, "badge", o), exist_ok=True)
        with open(os.path.join(ROOT, "badge", o, n + ".svg"), "w") as f:
            f.write(badge_svg(r, th))
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
<ol class="list ranked">{items}</ol>
""".format(base=BASE, label=E(label), color=color, key=E(key), blurb=E(blurb), count=len(items), updated=updated,
           items="".join(repo_card(x, th, BASE) for x in items[:150]))
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
