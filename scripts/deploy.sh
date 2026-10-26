#!/usr/bin/env bash
# One-command setup: creates the GitHub repo, pushes the site, turns on Pages and
# write access for the agents, and starts the first data scan.
# Needs the GitHub CLI logged in (`gh auth login`). Usage: bash scripts/deploy.sh [repo-name]
set -euo pipefail
NAME="${1:-star-catcher}"
cd "$(dirname "$0")/.."

OWNER="$(gh api user --jq .login)"
echo "Deploying to github.com/$OWNER/$NAME"

if [ ! -d .git ]; then
  git init -q -b main
  git add -A
  git commit -q -m "Star Catcher: initial site, data pipeline and agents"
fi

if gh repo view "$OWNER/$NAME" >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$NAME.git"
  git push -u origin main
else
  gh repo create "$NAME" --public --source . --remote origin --push
fi

echo "Giving workflows write access (needed to commit data and open issues)…"
gh api -X PUT "repos/$OWNER/$NAME/actions/permissions/workflow" \
  -f default_workflow_permissions=write -F can_approve_pull_request_reviews=false >/dev/null

echo "Turning on GitHub Pages…"
gh api -X POST "repos/$OWNER/$NAME/pages" -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 \
  || echo "Pages already on."

echo "Starting the first data scan…"
gh workflow run update.yml -R "$OWNER/$NAME" || echo "Open the Actions tab and run 'Update repo data' once."

URL="https://$(echo "$OWNER" | tr '[:upper:]' '[:lower:]').github.io/$NAME/"
echo
echo "Done. The site will be live at $URL in a few minutes."
echo "Optional: add ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN as a repo secret to switch on the debug agent."
