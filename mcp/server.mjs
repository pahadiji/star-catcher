#!/usr/bin/env node
// Star Catcher MCP server: lets Claude search every Claude, Claude Code, MCP and agent repo
// tracked by https://pahadiji.github.io/star-catcher/. One file, no dependencies (Node 18+).
// It only reads the site's public JSON. Transport: MCP over stdio (newline-delimited JSON-RPC).
//
//   Claude Code:  claude mcp add star-catcher -- node /path/to/server.mjs
//   Env: STAR_CATCHER_URL to point at another copy of the site (default below).

const BASE = (process.env.STAR_CATCHER_URL || "https://pahadiji.github.io/star-catcher/").replace(/\/?$/, "/");
const VERSION = "1.0.0";
const CATEGORIES = ["MCP Servers", "Skills & Plugins", "Agents & SDK", "Dev Tools & CLI", "Prompts & Guides", "Apps & UIs", "Other"];

const cache = {};
async function load(name, fallback) {
  const hit = cache[name];
  if (hit && Date.now() - hit.t < 36e5) return hit.v;
  try {
    const res = await fetch(BASE + "data/" + name, { headers: { "User-Agent": "star-catcher-mcp/" + VERSION } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const v = await res.json();
    cache[name] = { t: Date.now(), v };
    return v;
  } catch (e) {
    if (hit) return hit.v;
    if (fallback !== undefined) return fallback;
    throw new Error("Could not load " + name + " from " + BASE + ": " + e.message);
  }
}
const repos = async () => (await load("repos.json")).repos || [];
const page = r => BASE + "r/" + r.owner + "/" + r.name + "/";
const line = r => `- ${r.full_name} (★${r.stars}, ${r.category}): ${(r.description || "").slice(0, 160)}\n  GitHub: ${r.url} · Star Catcher: ${page(r)}`;
const matchCat = (r, c) => !c || (r.category || "").toLowerCase() === String(c).toLowerCase();
const clampN = (n, d, max) => Math.max(1, Math.min(max, Number.isFinite(+n) ? Math.floor(+n) : d));

const TOOLS = [
  {
    name: "search_repos",
    description: "Search Claude, Claude Code, MCP server, skill, plugin and agent repos on GitHub by keyword (name, description, topics). Results are ranked by keyword match, then GitHub stars.",
    inputSchema: { type: "object", properties: {
      query: { type: "string", description: "Keywords, e.g. 'postgres', 'browser automation', 'memory'" },
      category: { type: "string", enum: CATEGORIES, description: "Optional category filter" },
      limit: { type: "integer", minimum: 1, maximum: 25, default: 10 } }, required: ["query"] },
    async run({ query, category, limit }) {
      const words = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
      const scored = (await repos()).filter(r => matchCat(r, category)).map(r => {
        const hay = (r.full_name + " " + (r.description || "") + " " + (r.topics || []).join(" ")).toLowerCase();
        return [words.filter(w => hay.includes(w)).length, r];
      }).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0] || b[1].stars - a[1].stars).slice(0, clampN(limit, 10, 25));
      return scored.length ? `${scored.length} repos for "${query}":\n` + scored.map(([, r]) => line(r)).join("\n") : `No repos match "${query}". Try fewer or broader words.`;
    }
  },
  {
    name: "trending",
    description: "Claude / MCP / agent repos that gained the most GitHub stars this week.",
    inputSchema: { type: "object", properties: {
      category: { type: "string", enum: CATEGORIES }, limit: { type: "integer", minimum: 1, maximum: 25, default: 10 } } },
    async run({ category, limit }) {
      const hot = await load("trending.json", []);
      const by = Object.fromEntries((await repos()).map(r => [r.full_name, r]));
      const list = hot.filter(h => by[h.full_name] && matchCat(by[h.full_name], category)).slice(0, clampN(limit, 10, 25));
      return list.length ? "Trending this week (stars gained):\n" + list.map(h => `+${h.gain}★ ` + line(by[h.full_name]).slice(2)).join("\n") + `\nMore: ${BASE}trending/` : "No trending data yet.";
    }
  },
  {
    name: "repo_info",
    description: "Details for one repo tracked by Star Catcher, given 'owner/name'.",
    inputSchema: { type: "object", properties: { full_name: { type: "string", description: "owner/name, e.g. anthropics/claude-code" } }, required: ["full_name"] },
    async run({ full_name }) {
      const r = (await repos()).find(x => x.full_name.toLowerCase() === String(full_name || "").toLowerCase());
      if (!r) return `${full_name} is not tracked. Search with search_repos instead.`;
      const picks = (await load("picks.json", { picks: {} })).picks || {};
      const v = Object.values(picks).flat().find(p => p.full_name.toLowerCase() === r.full_name.toLowerCase());
      return [`${r.full_name}: ${r.description || ""}`, `Category: ${r.category} · ★${r.stars} · forks ${r.forks} · ${r.language || "n/a"} · licence ${r.license || "n/a"}`,
        `Topics: ${(r.topics || []).join(", ") || "none"}`, `Created ${String(r.created_at).slice(0, 10)} · last push ${String(r.pushed_at).slice(0, 10)}`,
        v ? `Verified by the ${v.senior}: ${v.reason}` : "", `GitHub: ${r.url}`, `Star Catcher: ${page(r)}`].filter(Boolean).join("\n");
    }
  },
  {
    name: "verified_picks",
    description: "New repos that Star Catcher's scout agents demoed and a category senior agent approved (valid SKILL.md / plugin manifest / MCP SDK, real README, licence, active).",
    inputSchema: { type: "object", properties: { category: { type: "string", enum: CATEGORIES } } },
    async run({ category }) {
      const picks = (await load("picks.json", { picks: {} })).picks || {};
      const out = Object.entries(picks).filter(([c]) => !category || c.toLowerCase() === category.toLowerCase())
        .flatMap(([c, items]) => items.map(p => `- [${c}] ${p.full_name} (★${p.stars}): ${p.reason}\n  ${p.url}`));
      return out.length ? out.join("\n") : "No verified picks yet.";
    }
  },
  {
    name: "list_topics",
    description: "Popular GitHub topics among Claude / MCP / agent repos, with how many repos use each.",
    inputSchema: { type: "object", properties: { limit: { type: "integer", minimum: 1, maximum: 100, default: 40 } } },
    async run({ limit }) {
      const t = await load("topics.json", {});
      return Object.entries(t).slice(0, clampN(limit, 40, 100)).map(([k, n]) => `${k} (${n}) ${BASE}t/${k}/`).join("\n") || "No topics yet.";
    }
  }
];

function send(msg) { process.stdout.write(JSON.stringify(msg) + "\n"); }
async function handle(m) {
  const { id, method, params } = m;
  if (id === undefined || id === null) return; // notifications need no reply
  const ok = result => send({ jsonrpc: "2.0", id, result });
  const err = (code, message) => send({ jsonrpc: "2.0", id, error: { code, message } });
  try {
    if (method === "initialize") return ok({ protocolVersion: (params && params.protocolVersion) || "2025-06-18", capabilities: { tools: {} },
      serverInfo: { name: "star-catcher", version: VERSION }, instructions: "Search Claude, Claude Code, MCP, skill and agent repos tracked by Star Catcher." });
    if (method === "ping") return ok({});
    if (method === "tools/list") return ok({ tools: TOOLS.map(({ run, ...t }) => t) });
    if (method === "tools/call") {
      const tool = TOOLS.find(t => t.name === (params && params.name));
      if (!tool) return err(-32602, "Unknown tool: " + (params && params.name));
      try { return ok({ content: [{ type: "text", text: await tool.run((params && params.arguments) || {}) }] }); }
      catch (e) { return ok({ content: [{ type: "text", text: "Error: " + e.message }], isError: true }); }
    }
    return err(-32601, "Method not found: " + method);
  } catch (e) { return err(-32603, e.message); }
}

let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => {
  buf += chunk;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const raw = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!raw) continue;
    let m;
    try { m = JSON.parse(raw); } catch { send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }); continue; }
    handle(m);
  }
});
