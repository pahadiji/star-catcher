// Headless smoke test for Star Catcher (run: npm test): boots the page in jsdom with a stub canvas,
// plays one full catch, and checks the codex, inventory and dialog.
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");
const ROOT = process.argv[2] || path.join(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true, url: "https://example.test/" });
const w = dom.window;
const noop = new Proxy(function () {}, { get: (t, k) => (k === "measureText" ? () => ({ width: 40 }) : k === "createRadialGradient" ? () => ({ addColorStop() {} }) : noop), apply: () => noop });
w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: (t, k) => (k === "measureText" ? () => ({ width: 40 }) : (k === "createRadialGradient" || k === "createLinearGradient") ? () => ({ addColorStop() {} }) : () => {}), set: () => true });
w.HTMLElement.prototype.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1000, height: 640, right: 1000, bottom: 640 });
w.ResizeObserver = class { constructor(cb) { this.cb = cb; } observe() { this.cb(); } };
w.matchMedia = () => ({ matches: false });
w.fetch = () => Promise.resolve({ json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(ROOT, "data/repos.json"), "utf8"))) });
w.HTMLCanvasElement.prototype.setPointerCapture = () => {};
const errors = [];
w.addEventListener("error", e => errors.push(e.message));
for (const f of ["config.js", "assets/sound.js", "assets/ads.js", "assets/app.js"]) {
  try { w.eval(fs.readFileSync(path.join(ROOT, f), "utf8")); } catch (e) { errors.push(f + ": " + e.message); }
}
const doc = w.document, $ = id => doc.getElementById(id);
const wait = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  await wait(300);
  let failed = 0;
  const check = (name, cond) => { if (!cond) failed++; console.log((cond ? "PASS " : "FAIL ") + name); };
  check("no boot errors", errors.length === 0);
  if (errors.length) console.log(errors);
  check("data note shows stars", /stars charted/.test($("data-note").textContent));
  check("universe has topic constellations", /[1-9]\d* constellations/.test($("data-note").textContent));
  console.log("  " + $("data-note").textContent);
  check("idle panel rendered", /Every repo is a star/.test($("panel").textContent));
  // search and select
  const s = $("search"); s.value = "claude-code"; s.dispatchEvent(new w.Event("input"));
  const hit = $("results").querySelector("button[data-id]");
  check("search finds claude-code", !!hit);
  const hitName = hit ? hit.querySelector("span").firstChild.textContent.trim() : "";
  hit.click();
  check("select panel shows repo", $("panel").textContent.includes(hitName) && /Inspect/.test($("panel").textContent));
  $("panel").querySelector('[data-act="inspect"]').click();
  check("inspect reveals details", /Language/.test($("panel").textContent));
  $("panel").querySelector('[data-act="catch"]').click();
  check("aim panel with throw button", !!$("throw-btn"));
  check("auto-picked a device", /Using/.test($("panel").textContent) && !/Using <b>nothing/.test($("panel").innerHTML));
  const before = $("inv").textContent;
  w.Math.random = () => 0; // force a successful catch
  $("throw-btn").click();
  check("throw consumes a device", $("inv").textContent !== before);
  await wait(1050 + 650 * 3 + 1100);
  check("caught dialog opened", !$("scrim").hidden && /Caught!/.test($("dialog").textContent));
  check("rewards shown first", /XP/.test($("dialog").querySelector(".rewards").textContent));
  // Escape closes
  $("dialog").dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  check("escape closes dialog", $("scrim").hidden);
  const saved = JSON.parse(w.localStorage.getItem("starcatcher:v1"));
  check("progress saved with 1 catch", Object.keys(saved.codex).length === 1 && saved.xp > 0);
  doc.querySelector('.tab[data-view="codex"]').click();
  check("codex lists the catch", $("codex-grid").querySelectorAll(".entry").length === 1);
  doc.querySelector('.tab[data-view="card"]').click();
  check("explorer card renders", /Share your sky/.test($("explorer").textContent));
  doc.querySelector('.tab[data-view="galaxy"]').click();
  // escape path: force failure
  const s2 = $("search"); s2.value = "servers"; s2.dispatchEvent(new w.Event("input"));
  // pick a result that is not caught yet, so the Catch button exists
  const hits2 = [...$("results").querySelectorAll("button[data-id]")];
  hits2.find(b => !JSON.parse(w.localStorage.getItem("starcatcher:v1")).codex[b.dataset.id]).click();
  const secondName = $("panel").querySelector("h2").textContent;
  $("panel").querySelector('[data-act="catch"]').click();
  w.Math.random = () => 0.999;
  $("throw-btn").click();
  await wait(1050 + 650 * 3 + 1100);
  check("fled panel offers retry", /broke free/.test($("panel").textContent));
  $("panel").querySelector('[data-act="run"]').click();
  check("back to browse", $("panel").textContent.includes(secondName) && /Catch this star/.test($("panel").textContent));
  check("no runtime errors", errors.length === 0);
  if (errors.length) console.log(errors);
  process.exit(failed ? 1 : 0);
})();
