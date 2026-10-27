# Star Catcher MCP server

Lets Claude search every Claude, Claude Code, MCP server, skill, plugin and agent repo on GitHub, using the public data of [Star Catcher](https://pahadiji.github.io/star-catcher/) (refreshed every 6 hours). One file, no dependencies, Node 18+. Read-only.

## Install

Claude Code:

```sh
claude mcp add star-catcher -- npx -y star-catcher-mcp
# or without npm:
curl -fsSL https://pahadiji.github.io/star-catcher/mcp/server.mjs -o ~/.star-catcher-mcp.mjs
claude mcp add star-catcher -- node ~/.star-catcher-mcp.mjs
```

Claude Desktop (`claude_desktop_config.json`):

```json
{ "mcpServers": { "star-catcher": { "command": "npx", "args": ["-y", "star-catcher-mcp"] } } }
```

## Tools

| Tool | What it does |
|---|---|
| `search_repos` | Find repos by keyword, optionally in one category |
| `trending` | Repos that gained the most stars this week |
| `repo_info` | Details for one `owner/name` |
| `verified_picks` | New repos approved by Star Catcher's senior agents |
| `list_topics` | Popular topics and their repo counts |

Try: "Use star-catcher to find an MCP server for Postgres".
