# Star Catcher

Every Claude, Claude Code, MCP, skill, plugin and agent repo on GitHub, shown as a galaxy you can explore and play.

- Each repo is a star with a face. Its size comes from GitHub stars, its colour from its constellation (category).
- Click a star to see it, **Inspect** it to read the repo, then **Catch** it with an original catch device.
- Caught stars go into your **Codex**; every 6-hour scan brings new stars, grows the ones you caught, and refills your devices.
- Sound effects are synthesized in the browser (no audio files). Motion and sound each have a toggle.
- Progress is saved in the visitor's browser. No accounts, no server, no database.

## Files

```
index.html                     page shell
config.js                      ads, sponsor, links, game tuning  <- edit this
assets/app.js                  galaxy (canvas), catch loop, codex, explorer card
assets/sound.js                synthesized sound effects (Web Audio)
assets/ads.js                  ad wrapper: H5 Games Ads + one display network
assets/style.css               styles
data/repos.json                galaxy data (sample until the first scan)
scripts/fetch_repos.py         GitHub search -> data/repos.json
scripts/health_check.py        health check agent
scripts/supervisor.py          supervisor agent (status board)
tests/smoke.js                 plays a full game headlessly (npm test)
CLAUDE.md                      rules the debug agent follows
.github/workflows/update.yml        data updater, every 6 hours
.github/workflows/health.yml        health check, every 12 hours
.github/workflows/debug-agent.yml   debug agent, on health/bug issues
.github/workflows/supervisor.yml    supervisor, daily
.github/workflows/test.yml          tests on every push and pull request
```

## Automation and agents

### The agent team

```
                              Overseer (Claude, twice a day) ── Supervisor (status board, daily)
                                             │
     ┌───────────────────────┬───────────────┼─────────────────────┬──────────────────────────┐
  Data team               Talent team                       Growth team                   Quality team
  Data updater (6h)       Skills scout ─┐                    Growth leads (daily, HN/Reddit) Tests (every push)
  Page builder (6h)       Plugins scout ├─ demo ─▶ Seniors:  Growth scout (Claude, daily:   Health check (12h)
                          Repos scout  ─┘   MCP · Skills &     drafts replies, Monday       Debug agent (on issues)
                                            plugins · Agents ·  sponsor prospects)           Traffic agent (daily:
                                            Dev tools ·        Promo kit (Mondays)            visitors, mentions,
                                            Guides · Apps      Posting: Bluesky/Mastodon      badges, diagnosis)
                                                               (each scan), dev.to (weekly)
```

- **Scouts** (`scripts/scouts.py`, `talent.yml`, daily) search GitHub for new skills, plugins and repos and demo each one by static inspection: the file list, the manifest that proves what it is (`SKILL.md` frontmatter, `.claude-plugin/plugin.json`, an MCP or Claude Agent SDK dependency), README, licence, activity and stars. They never run third-party code.
- **Senior agents** (`scripts/seniors.py`), one per category, approve up to 6 **Verified picks** each with written reasons and re-review them daily. Picks appear at the top of each category page and as a "✓ Verified" pill on repo pages.
- **Traffic agent** (`scripts/traffic_report.py`, `traffic.yml`, daily) keeps a **Growth report** issue: visitors, referrers, mentions on HN/Reddit, README badges, page checks, 14-day history and why the site is or isn't being found.
- **Posting agents** publish only where automated, clearly labelled posting is allowed and only with your keys: Bluesky / Mastodon (`BLUESKY_HANDLE` + `BLUESKY_APP_PASSWORD`, or `MASTODON_URL` + `MASTODON_TOKEN`) and a weekly dev.to roundup (`DEVTO_API_KEY`). Replies on Reddit, Hacker News and X stay human: the growth scout drafts them, you post them.

Everything runs inside GitHub, so nothing depends on your computer being on.

| Agent | When | What it does | Cost |
|---|---|---|---|
| **Data updater** (`update.yml`) | Every 6 hours | Searches GitHub for Claude repos, marks new and updated ones, commits `data/repos.json`, which redeploys the site. | Free |
| **Health check** (`health.yml`) | Every 12 hours | Checks the data is fresh and real, the site and its data load, and the updater's last run passed. Opens a `health` issue on failure and closes it when things recover. | Free |
| **Debug agent** (`debug-agent.yml`) | When a `health` or `bug` issue opens, or someone comments `@claude` | Claude reproduces the problem, makes the smallest fix, runs the tests and opens a pull request for you to merge. It never pushes to `main`. | Claude API or subscription usage |
| **Supervisor** (`supervisor.yml`) | Daily | Checks every other agent is running and succeeding, flags stalled or repeatedly failing ones and stuck health issues, and keeps one pinned **Status board** issue up to date. | Free |
| **Growth leads** (`growth-leads.yml`) | Daily | Collects Hacker News and Reddit threads from the last 48 hours where people ask about Claude tools, MCP servers, skills or agent frameworks, matches each to the best Star Catcher page, lists fast-growing repos whose owners may reshare, and opens one `Growth leads — <date>` issue. Read-only on other sites: it never posts. | Free |
| **Tests** (`test.yml`) | Every push and pull request | Syntax checks plus a headless game: search, inspect, catch, escape, codex, explorer card. | Free |

### Turning on the debug agent
1. Install the Claude GitHub App on the repo: https://github.com/apps/claude
2. Add one repository secret (**Settings → Secrets and variables → Actions**):
   - `ANTHROPIC_API_KEY` from https://platform.claude.com, or
   - `CLAUDE_CODE_OAUTH_TOKEN` from running `claude setup-token` (uses your Claude subscription).
3. Without a secret the workflow skips quietly; the other agents still run.

### Optional
- Set the repository variable `SITE_URL` (Settings → Secrets and variables → Actions → Variables) if you use a custom domain, so the health check tests the right address.
- Watch the repo (Watch → Custom → Issues) to get an email when the health check or supervisor raises something.
- GitHub pauses scheduled workflows in a public repo after 60 days without activity. The data updater commits every 6 hours, which keeps the schedules alive.

## Put it online (free, about 10 minutes)

1. Create a **public** GitHub repo and upload every file, keeping the folders (including `.github/`).
2. Repo **Settings → Actions → General → Workflow permissions**: choose **Read and write permissions** and save.
3. Repo **Settings → Pages**: deploy from branch `main`, folder `/ (root)`.
4. **Actions** tab → **Update repo data** → **Run workflow**. The first scan takes about 5–10 minutes and replaces the sample data with real repos.
5. Open `https://YOURNAME.github.io/REPO/`. From now on it refreshes itself every 6 hours.
6. Buy a domain (around ₹800/year) and add it under **Settings → Pages → Custom domain**. Ad networks and sponsors take a custom domain much more seriously.

## Earning from it

The site is built so ads never interrupt a throw. Turn each source on in `config.js`.

| Source | Where it shows | What you need | Notes |
|---|---|---|---|
| **Sponsored star** | A golden "Sponsored" star in the centre of the galaxy, plus a sponsor card in the side panel | Nothing — sell it directly. The `advertise/` page shows live numbers, and requests arrive through the "Sponsor / advertise" issue form | Highest earner for a niche dev site. Pitch AI dev-tool companies once you have traffic numbers. Clearly labelled, links use `rel="sponsored"`. |
| **Rewarded ads** (Google H5 Games Ads) | "Watch a short ad for +3 Commit Cubes" when a player runs low | AdSense account approved for H5 Games Ads | Opt-in only. The game shows the offer only when Google says an ad is available. |
| **Interstitials** (H5 Games Ads, `next`) | After closing a catch card, every 3rd catch (`interstitialEvery`) | Same as above | Google's rules forbid full-screen ads during continuous gameplay or right after another full-screen ad; this placement is a natural break. |
| **Display ad** | One unit in the sidebar, one in the footer | AdSense, **Carbon Ads** or **EthicalAds** | Carbon and EthicalAds pay better for developer audiences. EthicalAds asks for about 50,000 pageviews/month. |
| **Newsletter** | "Weekly new stars" box | Beehiiv / Substack link | Sell newsletter sponsorships later; the site already knows each week's new stars. |
| **Support button** | Header | Buy Me a Coffee / GitHub Sponsors / UPI link | |

### Turning on Google H5 Games Ads
1. Get an AdSense account for your domain, then sign up for H5 Games Ads.
2. In `config.js` set `ads.h5.enabled: true` and your `client` (`ca-pub-…`).
3. Keep `testMode: true` while testing (it adds `data-adbreak-test="on"`), then set it to `false` once approved.

### Rules worth knowing
- Never ask players to click ads, and rewards must not have real-world value.
- Carbon allows only its own ad on the page and expects it visible on first load; set `display.type` to one network only.
- Add analytics (Plausible or Google Analytics) in `index.html` so you can show sponsors real numbers.

## Getting players

- Launch posts: r/ClaudeAI, r/ClaudeCode, r/mcp, Hacker News "Show HN", X and LinkedIn.
- The Explorer card has "Post on X" with the player's catches — every share links back to the site.
- Post "This week's new stars" every Monday; the data already tags them.

## Customize

- Search terms and categories: `QUERIES` and `CATEGORIES` in `scripts/fetch_repos.py`.
- How many stars are drawn: `game.maxStarsOnMap` in `config.js` (biggest repos plus every new one).
- Starting devices and free refill timer: `game.startDevices`, `game.freeRefillHours`.

## Notes

- The catch devices (Commit Cube, Branch Orb, Bracket Trap, Release Capsule) and the star characters are original designs. Keep it that way: using another franchise's creatures, ball or name would put your domain and ad accounts at risk.
- Not affiliated with Anthropic or GitHub. Data comes from the public GitHub API.

## Growth engine (automatic)

Runs on every 6-hour scan, with no spam and nothing that risks your accounts or ad approval:

| What | How it brings visitors |
|---|---|
| **A page per repo** (`r/<owner>/<repo>/`) | ~2,700 pages that rank in Google for searches like "<repo> claude", "<name> mcp server". Each has title, description, stats, related repos and structured data. |
| **"Best X for Claude" lists** (`c/<category>/`) | Rank for "best MCP servers", "Claude Code skills", "Claude agents" — the searches people actually make. |
| **README badges** (`badge/<owner>/<repo>.svg`) | Repo owners add the badge to their README: a backlink plus visitors from every repo that shows it. |
| **New this week** (`new/`) + **RSS** (`feed.xml`) | Fresh content every 6 hours; RSS readers and aggregators pick it up. |
| **sitemap.xml + robots.txt** | Lets Google find every page. Submit the sitemap once in Google Search Console. |
| **IndexNow ping** | Tells Bing, Yandex and others about new pages within minutes of each scan. |
| **Deep links** (`?star=owner/repo`) | Every page, badge and post opens the galaxy flying straight to that star. |
| **Bluesky / Mastodon highlight** (optional) | One post per scan (max 4/day) about the best new repo. Add secrets `BLUESKY_HANDLE` + `BLUESKY_APP_PASSWORD` and/or `MASTODON_URL` + `MASTODON_TOKEN`. |
| **Weekly promo kit** (Mondays) | An issue with a ready X thread, Reddit post, LinkedIn post, newsletter section and the owners to tag. About 10 minutes of copy-paste a week. |

Turn on free analytics (GoatCounter) in `config.js` → `analytics.goatcounter` so you can show sponsors real numbers.
