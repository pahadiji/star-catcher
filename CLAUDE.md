# Star Catcher — notes for Claude agents

Static site on GitHub Pages. No build step, no server, no framework.

- `index.html`, `assets/*.js`, `assets/style.css`, `config.js`: the site. `assets/app.js` holds the canvas galaxy and the catch game.
- `data/repos.json`: written only by `scripts/fetch_repos.py` via the "Update repo data" workflow. Never edit it by hand.
- `scripts/health_check.py`: 12-hour health check; `--no-issue` prints the report without touching issues.
- `scripts/supervisor.py`: daily status board.
- `scripts/growth_leads.py`: daily growth-leads issue (read-only on HN/Reddit); `--no-issue` prints it.
- Tests: `npm install && npm test` (plays a full game headlessly) and `python -m py_compile scripts/*.py`.

Rules for changes:
- Smallest fix for the reported problem; keep the existing style (vanilla JS, no new dependencies in the site).
- Escape any repo-derived text before putting it in HTML (`esc()` in app.js).
- Do not change ad settings, the sponsor block or links in `config.js`.
- Never push to `main`; open a pull request.
