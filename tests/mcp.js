// Talks to mcp/server.mjs over stdio like Claude would, against this checkout's data/
// served on a local port. Run: node tests/mcp.js
const http = require("http"), fs = require("fs"), path = require("path"), { spawn } = require("child_process");
const ROOT = path.join(__dirname, "..");
const srv = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, ""));
  if (!f.startsWith(ROOT) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "Content-Type": "application/json" }); fs.createReadStream(f).pipe(res);
}).listen(0, async () => {
  const p = spawn(process.execPath, [path.join(ROOT, "mcp/server.mjs")], { env: { ...process.env, STAR_CATCHER_URL: "http://127.0.0.1:" + srv.address().port + "/" } });
  let out = "", failed = 0;
  const waiters = {};
  p.stdout.on("data", d => { out += d; let i; while ((i = out.indexOf("\n")) >= 0) { const m = JSON.parse(out.slice(0, i)); out = out.slice(i + 1); if (waiters[m.id]) waiters[m.id](m); } });
  let n = 0;
  const call = (method, params) => new Promise(r => { const id = ++n; waiters[id] = r; p.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n"); });
  const check = (name, cond, extra) => { if (!cond) failed++; console.log((cond ? "PASS " : "FAIL ") + name + (cond || !extra ? "" : " :: " + extra)); };
  const init = await call("initialize", { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "1" } });
  check("initialize", init.result && init.result.serverInfo.name === "star-catcher");
  p.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
  const list = await call("tools/list", {});
  check("five tools", list.result && list.result.tools.length === 5);
  const text = async (name, args) => { const r = await call("tools/call", { name, arguments: args }); return r.result ? r.result.content[0].text : JSON.stringify(r.error); };
  const s = await text("search_repos", { query: "claude code", limit: 3 });
  check("search finds repos", /★/.test(s) && /Star Catcher: http/.test(s), s.slice(0, 200));
  const info = await text("repo_info", { full_name: "anthropics/claude-code" });
  check("repo_info", /anthropics\/claude-code/.test(info), info.slice(0, 200));
  check("trending answers", (await text("trending", {})).length > 10);
  check("verified_picks answers", (await text("verified_picks", {})).length > 10);
  check("list_topics answers", (await text("list_topics", { limit: 5 })).length > 5);
  const bad = await call("tools/call", { name: "nope", arguments: {} });
  check("unknown tool is an error", !!bad.error);
  p.kill(); srv.close();
  process.exit(failed ? 1 : 0);
});
