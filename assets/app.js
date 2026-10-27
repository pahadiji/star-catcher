/*
 * Star Catcher — game and galaxy.
 * Reads data/repos.json (written every 6 hours by the GitHub Action), lays every
 * repo out as a star in a spiral-armed constellation, and runs the catch loop.
 * Progress is saved in this browser only (localStorage).
 */
(function () {
  "use strict";

  const CFG = window.SITE_CONFIG || {};
  const GAME = CFG.game || {};
  const DAY = 864e5;
  const TAU = Math.PI * 2;
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = n => (n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n || 0));
  const safeUrl = u => (typeof u === "string" && /^https:\/\/github\.com\//.test(u) ? u : "#");
  const ago = d => {
    if (!d) return "unknown";
    const s = (Date.now() - new Date(d)) / 1000;
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + "m ago";
    if (s < 86400) return Math.round(s / 3600) + "h ago";
    if (s < 2592000) return Math.round(s / 86400) + "d ago";
    return Math.round(s / 2592000) + "mo ago";
  };
  const hash = str => { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
  const rng = seed => () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const easeOutBack = p => { const c = 1.70158; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); };
  const mix = (a, b, t) => {
    const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
    const ch = s => Math.round(((pa >> s) & 255) * (1 - t) + ((pb >> s) & 255) * t);
    return "#" + ((1 << 24) | (ch(16) << 16) | (ch(8) << 8) | ch(0)).toString(16).slice(1).toUpperCase();
  };
  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Game rules ----------
  const CATS = [
    { key: "MCP Servers", label: "MCP Nebula", color: "#4DA8FF", alt: "#7B6CFF", badge: "Socket Badge" },
    { key: "Agents & SDK", label: "Agent Cluster", color: "#A77BFF", alt: "#FF6FD8", badge: "Loop Badge" },
    { key: "Skills & Plugins", label: "Skills Belt", color: "#FF8A3D", alt: "#FFD23F", badge: "Spark Badge" },
    { key: "Dev Tools & CLI", label: "Tools System", color: "#3DE0C0", alt: "#4DA8FF", badge: "Forge Badge" },
    { key: "Prompts & Guides", label: "Guide Station", color: "#FF5FA2", alt: "#FF8A3D", badge: "Scroll Badge" },
    { key: "Apps & UIs", label: "App Colony", color: "#FFD23F", alt: "#FF8A3D", badge: "Pixel Badge" },
    { key: "Other", label: "Outer Rim", color: "#9BE15D", alt: "#3DE0C0", badge: "Drift Badge" }
  ];
  const CAT_BY = {};
  CATS.forEach((c, i) => { c.i = i; c.dark = mix(c.color, "#07070F", 0.62); CAT_BY[c.key] = c; });
  const DEV = {
    cube: { name: "Commit Cube", bonus: 0, color: "#2EC4B6" },
    orb: { name: "Branch Orb", bonus: 0.15, color: "#9B5DE5" },
    brace: { name: "Bracket Trap", bonus: 0.3, color: "#FF7A3D" },
    cap: { name: "Release Capsule", bonus: 0.5, color: "#E8E6F5" }
  };
  const DEV_KEYS = ["cube", "orb", "brace", "cap"];
  const BADGE_AT = 5;

  // Rarity follows the real distribution: top 2% Legendary, next 8% Epic, next 25% Rare.
  // Thresholds are recomputed from the data on load (these are fallbacks).
  const TH = { L: 20000, E: 5000, R: 500 };
  const rank = n => n >= TH.L ? { k: "Legendary", rings: 2, zone: 12, base: 0.3, xp: 120 }
    : n >= TH.E ? { k: "Epic", rings: 1, zone: 18, base: 0.45, xp: 80 }
    : n >= TH.R ? { k: "Rare", rings: 0, zone: 26, base: 0.6, xp: 50 }
    : { k: "Common", rings: 0, zone: 34, base: 0.8, xp: 30 };
  const stage = n => (n >= 10000 ? 3 : n >= 1000 ? 2 : 1);
  const stageName = n => ["", "Protostar", "Star", "Giant"][stage(n)];
  const levelInfo = xp => { let L = 1, need = 100, x = xp; while (x >= need) { x -= need; L++; need = Math.round(need * 1.25); } return { level: L, into: x, need: need }; };

  // ---------- Saved progress ----------
  const KEY = "starcatcher:v1";
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY)); } catch (e) { saved = null; }
  const S = Object.assign({
    codex: {}, seen: {}, inv: Object.assign({ cube: 10, orb: 3, brace: 1, cap: 0 }, GAME.startDevices || {}),
    xp: 0, thrown: 0, catches: 0, badges: {}, trainer: "Explorer", sound: false, motion: !reducedMotion,
    lastData: null, lastRefill: 0
  }, saved || {});
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* private mode */ } };

  // ---------- Runtime ----------
  const R = {
    data: null, stars: [], byId: {}, view: "galaxy", sel: null, mode: "browse",
    cam: { x: 0, y: 0, z: 0.5 }, goal: null, m: 0, dir: 1, dev: null, pickerOpen: false,
    hover: null, hoverT: 0, anim: null, particles: [], trail: [], meteors: [], timers: [], rewardShow: null, rewardAsked: false,
    fresh: false, rewards: [], copied: false, W: 0, H: 0, dpr: 1, inZone: false, introT0: 0, lastInput: 0, nextMeteor: 0, flash: null
  };
  const later = (fn, ms) => R.timers.push(setTimeout(fn, ms));

  // ---------- Canvas ----------
  const canvas = $("sky");
  const ctx = canvas.getContext("2d");
  const LAYERS = [0.04, 0.1, 0.2].map((f, li) => ({ f: f, dots: Array.from({ length: [220, 120, 50][li] }, (_, i) => ({ x: (hash("x" + li + i) % 10000) / 10000, y: (hash("y" + li + i) % 10000) / 10000, p: (hash("p" + li + i) % 628) / 100, c: ["#FFFFFF", "#BFD4FF", "#FFE7C2", "#E9D6FF"][hash("c" + li + i) % 4] })) }));
  const spriteCache = new Map();
  const texCache = new Map();

  function resize() {
    const rect = canvas.getBoundingClientRect();
    R.dpr = Math.min(2, window.devicePixelRatio || 1);
    R.W = rect.width; R.H = rect.height;
    canvas.width = Math.round(rect.width * R.dpr);
    canvas.height = Math.round(rect.height * R.dpr);
    ctx.setTransform(R.dpr, 0, 0, R.dpr, 0, 0);
    spriteCache.clear();
  }
  new ResizeObserver(resize).observe(canvas);

  function offscreen(w, h) { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; }

  // Soft, cloudy nebula built from many overlapping blobs, cached per constellation.
  function nebulaTex(c) {
    if (texCache.has(c.key)) return texCache.get(c.key);
    const N = 384, cv = offscreen(N, N), g = cv.getContext("2d"), rnd = rng(hash(c.key));
    g.globalCompositeOperation = "lighter";
    for (let i = 0; i < 90; i++) {
      const a = rnd() * TAU, d = Math.pow(rnd(), 1.6) * N * 0.34, x = N / 2 + Math.cos(a) * d, y = N / 2 + Math.sin(a) * d * 0.8;
      const r = N * (0.06 + rnd() * 0.16), col = rnd() < 0.65 ? c.color : c.alt;
      const gr = g.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, col + (rnd() < 0.2 ? "2A" : "16")); gr.addColorStop(1, col + "00");
      g.fillStyle = gr; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    texCache.set(c.key, cv);
    return cv;
  }
  function bandTex() {
    if (texCache.has("band")) return texCache.get("band");
    const W = 640, H = 200, cv = offscreen(W, H), g = cv.getContext("2d"), rnd = rng(7);
    g.globalCompositeOperation = "lighter";
    for (let i = 0; i < 140; i++) {
      const x = rnd() * W, y = H / 2 + (rnd() - 0.5) * H * 0.5 * (1 - Math.abs(x / W - 0.5)), r = 20 + rnd() * 60;
      const gr = g.createRadialGradient(x, y, 0, x, y, r);
      const col = ["#6B5BFF", "#3B6BFF", "#B05BFF", "#FF7AB8"][Math.floor(rnd() * 4)];
      gr.addColorStop(0, col + "14"); gr.addColorStop(1, col + "00");
      g.fillStyle = gr; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    for (let i = 0; i < 500; i++) { g.fillStyle = "rgba(255,255,255," + (0.15 + rnd() * 0.4) + ")"; const x = rnd() * W, y = H / 2 + (rnd() - 0.5) * H * 0.45 * (1 - Math.abs(x / W - 0.5) * 1.4); g.fillRect(x, y, 1, 1); }
    // Feather every edge so the band never shows a hard rectangle.
    g.globalCompositeOperation = "destination-in";
    const vy = g.createLinearGradient(0, 0, 0, H); vy.addColorStop(0, "rgba(0,0,0,0)"); vy.addColorStop(0.5, "rgba(0,0,0,1)"); vy.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = vy; g.fillRect(0, 0, W, H);
    const vx = g.createLinearGradient(0, 0, W, 0); vx.addColorStop(0, "rgba(0,0,0,0)"); vx.addColorStop(0.2, "rgba(0,0,0,1)"); vx.addColorStop(0.8, "rgba(0,0,0,1)"); vx.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = vx; g.fillRect(0, 0, W, H);
    texCache.set("band", cv);
    return cv;
  }

  // Pre-rendered glow + glossy body for each colour and size.
  function sprite(color, r) {
    const key = color + r;
    let sp = spriteCache.get(key);
    if (sp) return sp;
    const size = Math.ceil(r * 5 + 4), cv = offscreen(Math.ceil(size * R.dpr), Math.ceil(size * R.dpr));
    const g = cv.getContext("2d");
    g.scale(R.dpr, R.dpr);
    const m = size / 2;
    const glow = g.createRadialGradient(m, m, r * 0.5, m, m, r * 2.5);
    glow.addColorStop(0, color + "70"); glow.addColorStop(0.4, color + "22"); glow.addColorStop(1, color + "00");
    g.fillStyle = glow; g.beginPath(); g.arc(m, m, r * 2.5, 0, TAU); g.fill();
    const body = g.createRadialGradient(m - r * 0.35, m - r * 0.45, r * 0.05, m, m, r);
    body.addColorStop(0, "#FFFFFF"); body.addColorStop(0.32, mix(color, "#FFFFFF", 0.35)); body.addColorStop(0.75, color); body.addColorStop(1, mix(color, "#07070F", 0.45));
    g.fillStyle = body; g.beginPath(); g.arc(m, m, r, 0, TAU); g.fill();
    g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = Math.max(1, r * 0.06); g.beginPath(); g.arc(m, m, r * 0.92, Math.PI * 1.1, Math.PI * 1.55); g.stroke();
    sp = { c: cv, size: size };
    spriteCache.set(key, sp);
    return sp;
  }

  const toScreen = (x, y) => [(x - R.cam.x) * R.cam.z + R.W / 2, (y - R.cam.y) * R.cam.z + R.H / 2];
  const toWorld = (sx, sy) => [(sx - R.W / 2) / R.cam.z + R.cam.x, (sy - R.H / 2) / R.cam.z + R.cam.y];

  // ---------- Data → stars ----------
  function build(data) {
    const now = Date.now();
    const isNew = r => r.created_at && now - new Date(r.created_at) < 14 * DAY; // created on GitHub in the last 14 days
    const repos = (data.repos || []).filter(r => r && r.full_name).sort((a, b) => b.stars - a.stars);
    const pick = repos.slice(0, GAME.maxStarsOnMap || 700);
    const ids = new Set(pick.map(r => String(r.id)));
    const wanted = deepLink();
    repos.forEach(r => { const id = String(r.id); if (!ids.has(id) && (isNew(r) || S.codex[id] || r.full_name.toLowerCase() === wanted)) { pick.push(r); ids.add(id); } });

    if (repos.length >= 20) {
      const at = p => repos[Math.min(repos.length - 1, Math.floor(repos.length * p))].stars || 0;
      TH.L = Math.max(10, at(0.02)); TH.E = Math.max(5, at(0.10)); TH.R = Math.max(2, at(0.35));
    }
    const groups = {};
    pick.forEach(r => { const c = CAT_BY[r.category] || CAT_BY.Other; (groups[c.key] = groups[c.key] || []).push(r); });
    const biggest = Math.max(1, ...CATS.map(c => (groups[c.key] || []).length));
    const ring = 600 + 40 * Math.sqrt(biggest);
    const stars = [];
    CATS.forEach(c => {
      const list = (groups[c.key] || []).sort((a, b) => b.stars - a.stars);
      const ang = -Math.PI / 2 + (c.i * TAU) / CATS.length;
      c.cx = Math.cos(ang) * ring * 1.3; c.cy = Math.sin(ang) * ring;
      c.count = list.length;
      c.radius = 80 + 36 * Math.sqrt(list.length);
      const arms = list.length > 40 ? 3 : 2, twist = 2.6 + (c.i % 3) * 0.5, rnd = rng(hash(c.key));
      const mine = list.map((r, i) => {
        let x = c.cx, y = c.cy;
        if (i) {
          const t = Math.sqrt(i / list.length), arm = i % arms;
          const rad = 36 + c.radius * t, th = (arm * TAU) / arms + t * twist + (rnd() - 0.5) * 0.5;
          x += Math.cos(th) * rad + (rnd() - 0.5) * 22; y += Math.sin(th) * rad * 0.78 + (rnd() - 0.5) * 22;
        }
        const h = hash(r.full_name);
        return {
          id: String(r.id), r: r, cat: c, x: x, y: y, size: 6 + Math.log10((r.stars || 0) + 1) * 3.4,
          phase: (h % 628) / 100, face: h % 5, tint: [c.color, mix(c.color, c.alt, 0.35), mix(c.color, "#FFFFFF", 0.25)][(h >>> 3) % 3],
          isNew: !!isNew(r), isUpd: !!(r.pushed_at && now - new Date(r.pushed_at) < 2 * DAY)
        };
      });
      // Gentle relaxation so neighbouring stars never overlap.
      for (let it = 0; it < 4; it++) for (let a = 1; a < mine.length; a++) for (let b = 0; b < a; b++) {
        const A = mine[a], B = mine[b], dx = A.x - B.x, dy = A.y - B.y, d = Math.hypot(dx, dy) || 1, min = (A.size + B.size) * 1.6;
        if (d < min) { const push = (min - d) / d; A.x += dx * push; A.y += dy * push; }
      }
      mine.forEach(s => stars.push(s));
    });
    if (CFG.sponsor) stars.push({ id: "sponsor", sponsor: true, x: 0, y: 0, size: 26, phase: 0, face: 0, tint: "#FFD23F", cat: { color: "#FFD23F", alt: "#FF8A3D", dark: "#8A6A00", label: "Sponsored" }, r: { name: CFG.sponsor.name, stars: 0 } });
    const maxD = Math.max(...stars.map(s => Math.hypot(s.x, s.y))) || 1;
    stars.forEach(s => { s.delay = (Math.hypot(s.x, s.y) / maxD) * 1100 + (hash(s.id) % 200); });
    R.stars = stars;
    R.byId = {};
    stars.forEach(s => { R.byId[s.id] = s; });
    // Intro: start far out, then swoop in while stars pop into place.
    const fit = fitView();
    R.cam = { x: fit.x, y: fit.y + 200, z: fit.z * 0.45 };
    R.introT0 = performance.now();
    glide(fit.x, fit.y, fit.z, !S.motion);
  }

  function fitView() {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    R.stars.forEach(s => { x0 = Math.min(x0, s.x); y0 = Math.min(y0, s.y); x1 = Math.max(x1, s.x); y1 = Math.max(y1, s.y); });
    const z = clamp(Math.min((R.W || 800) / (x1 - x0 + 260), (R.H || 600) / (y1 - y0 + 460)), 0.1, 1.2);
    return { x: (x0 + x1) / 2, y: (y0 + y1) / 2 + 40, z: z };
  }
  function glide(x, y, z, instant) {
    if (instant || !S.motion) { R.cam = { x: x, y: y, z: z }; R.goal = null; }
    else R.goal = { x: x, y: y, z: z };
  }
  function zoomAt(f, sx, sy) {
    const [wx, wy] = toWorld(sx, sy);
    const z = clamp(R.cam.z * f, 0.08, 4);
    R.goal = null;
    R.cam.z = z;
    R.cam.x = wx - (sx - R.W / 2) / z;
    R.cam.y = wy - (sy - R.H / 2) / z;
  }

  // ---------- Drawing ----------
  function popScale(s, now) {
    if (!S.motion) return 1;
    const p = (now - R.introT0 - s.delay) / 520;
    return p >= 1 ? 1 : p <= 0 ? 0 : easeOutBack(p);
  }

  function sparkle(x, y, r, color, alpha, rot) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot || 0); ctx.globalAlpha = alpha; ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < 4; i++) { const a = (i * TAU) / 4; ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); ctx.lineTo(Math.cos(a + TAU / 8) * r * 0.22, Math.sin(a + TAU / 8) * r * 0.22); }
    ctx.closePath(); ctx.fill(); ctx.restore(); ctx.globalAlpha = 1;
  }

  function drawFace(sx, sy, r, s, t, excited) {
    const ink = "#120E24";
    const blink = S.motion && !excited && ((t / 1000 + s.phase * 1.7) % 4.6) < 0.12;
    const ex = r * 0.3, ey = sy - r * 0.06, face = s.sponsor ? 0 : s.face;
    ctx.fillStyle = ink; ctx.strokeStyle = ink; ctx.lineCap = "round";
    const lw = Math.max(1.2, r * 0.08);
    const eye = (x, wink) => {
      if (blink || wink || face === 4) { ctx.lineWidth = lw; ctx.beginPath(); ctx.arc(x, ey + r * 0.02, r * 0.11, Math.PI * 1.1, Math.PI * 1.9, false); ctx.stroke(); return; }
      const big = excited ? 1.25 : 1;
      ctx.beginPath(); ctx.ellipse(x, ey, r * 0.115 * big, r * 0.16 * big, 0, 0, TAU); ctx.fill();
      if (r >= 11) { ctx.fillStyle = "#FFFFFF"; ctx.beginPath(); ctx.arc(x + r * 0.035, ey - r * 0.06, r * 0.045 * big, 0, TAU); ctx.fill(); ctx.fillStyle = ink; }
    };
    eye(sx - ex, false); eye(sx + ex, face === 2);
    if (r >= 10) {
      ctx.lineWidth = lw; ctx.beginPath();
      const my = sy + r * 0.2;
      if (excited || face === 1) { ctx.ellipse(sx, my + r * 0.02, r * 0.09, r * 0.11, 0, 0, TAU); ctx.fill(); }
      else if (face === 3) { ctx.arc(sx - r * 0.08, my, r * 0.08, 0.1 * Math.PI, 0.9 * Math.PI); ctx.moveTo(sx + r * 0.16, my); ctx.arc(sx + r * 0.08, my, r * 0.08, 0.1 * Math.PI, 0.9 * Math.PI); ctx.stroke(); }
      else { ctx.arc(sx, my - r * 0.04, r * 0.13, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke(); }
    }
    if (r >= 13) { ctx.fillStyle = "rgba(255,110,170,.42)"; ctx.beginPath(); ctx.ellipse(sx - r * 0.5, sy + r * 0.14, r * 0.13, r * 0.075, 0, 0, TAU); ctx.ellipse(sx + r * 0.5, sy + r * 0.14, r * 0.13, r * 0.075, 0, 0, TAU); ctx.fill(); }
  }

  function drawDevice(kind, x, y, size, rot, glow) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot || 0);
    const h = size / 2, col = DEV[kind].color;
    ctx.shadowColor = glow || col; ctx.shadowBlur = size * 0.6;
    if (kind === "cube") {
      const w = h * 0.95;
      ctx.fillStyle = "#8FF0E6"; ctx.beginPath(); ctx.moveTo(0, -h); ctx.lineTo(w, -h * 0.5); ctx.lineTo(0, 0); ctx.lineTo(-w, -h * 0.5); ctx.closePath(); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "#2EC4B6"; ctx.beginPath(); ctx.moveTo(-w, -h * 0.5); ctx.lineTo(0, 0); ctx.lineTo(0, h); ctx.lineTo(-w, h * 0.5); ctx.closePath(); ctx.fill();
      ctx.fillStyle = "#17867C"; ctx.beginPath(); ctx.moveTo(w, -h * 0.5); ctx.lineTo(0, 0); ctx.lineTo(0, h); ctx.lineTo(w, h * 0.5); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = "#07070F"; ctx.lineWidth = Math.max(1.5, size * 0.06);
      ctx.beginPath(); ctx.arc(w * 0.5, h * 0.25, size * 0.09, 0, TAU); ctx.moveTo(w * 0.12, h * 0.06); ctx.lineTo(w * 0.32, h * 0.16); ctx.moveTo(w * 0.68, h * 0.34); ctx.lineTo(w * 0.88, h * 0.44); ctx.stroke();
    } else if (kind === "orb") {
      const g = ctx.createRadialGradient(-h * 0.35, -h * 0.4, 1, 0, 0, h);
      g.addColorStop(0, "#F3EAFF"); g.addColorStop(0.35, "#B88BFF"); g.addColorStop(1, "#4A1F94");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, h, 0, TAU); ctx.fill();
      ctx.shadowBlur = 0; ctx.strokeStyle = "#FFD23F"; ctx.lineWidth = size * 0.07; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(-h * 0.3, -h * 0.5); ctx.lineTo(-h * 0.3, h * 0.5); ctx.moveTo(h * 0.35, -h * 0.25); ctx.quadraticCurveTo(h * 0.35, h * 0.3, -h * 0.3, h * 0.32); ctx.stroke();
      ctx.fillStyle = "#FFD23F"; [[-0.3, -0.5], [-0.3, 0.5], [0.35, -0.25]].forEach(([a, b]) => { ctx.beginPath(); ctx.arc(a * h, b * h, size * 0.07, 0, TAU); ctx.fill(); });
    } else if (kind === "brace") {
      ctx.strokeStyle = "#FF7A3D"; ctx.lineWidth = size * 0.13; ctx.lineCap = "round"; ctx.lineJoin = "round";
      const brace = sgn => { ctx.beginPath(); ctx.moveTo(sgn * h * 0.35, -h); ctx.bezierCurveTo(sgn * h * 0.75, -h, sgn * h * 0.55, -h * 0.25, sgn * h * 0.95, 0); ctx.bezierCurveTo(sgn * h * 0.55, h * 0.25, sgn * h * 0.75, h, sgn * h * 0.35, h); ctx.stroke(); };
      ctx.save(); ctx.scale(-1, 1); brace(-1); ctx.restore();
      brace(-1);
      ctx.shadowBlur = 0; ctx.fillStyle = "#FFD23F"; ctx.fillRect(-size * 0.09, -size * 0.09, size * 0.18, size * 0.18);
    } else {
      ctx.fillStyle = "#F7F5FF"; roundRect(-h * 0.62, -h, h * 0.62, size, h * 0.62); ctx.fill();
      ctx.shadowBlur = 0; ctx.fillStyle = "#9A98B3"; roundRect(0, -h, h * 0.62, size, h * 0.62); ctx.fill();
      ctx.fillStyle = "#FFD23F"; ctx.font = "700 " + Math.round(size * 0.22) + "px 'Space Grotesk', sans-serif"; ctx.textAlign = "center"; ctx.fillText("v1", h * 0.62, -h * 0.65);
    }
    ctx.restore();
  }
  function roundRect(x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  function drawSky(t) {
    const W = R.W, H = R.H, z = R.cam.z;
    const bg = ctx.createRadialGradient(W * 0.5, H * 0.45, 0, W * 0.5, H * 0.45, Math.max(W, H) * 0.8);
    bg.addColorStop(0, "#151030"); bg.addColorStop(0.55, "#0A0918"); bg.addColorStop(1, "#04040A");
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
    // Parallax star layers.
    LAYERS.forEach((L, li) => {
      L.dots.forEach(d => {
        const x = (((d.x * W - R.cam.x * z * L.f) % W) + W) % W, y = (((d.y * H - R.cam.y * z * L.f) % H) + H) % H;
        const tw = S.motion ? 0.5 + 0.5 * Math.sin(t / (700 + li * 300) + d.p) : 0.7;
        ctx.globalAlpha = (0.25 + li * 0.2) * tw + 0.1; ctx.fillStyle = d.c;
        const s = 0.6 + li * 0.55;
        ctx.fillRect(x, y, s, s);
        if (li === 2 && tw > 0.85) sparkle(x, y, 4, d.c, (tw - 0.85) * 4, 0);
      });
    });
    ctx.globalAlpha = 1;
    // A faint galactic band behind everything.
    const band = bandTex(), [bx, by] = toScreen(0, 0), bw = 3600 * z, bh = 1100 * z;
    ctx.save(); ctx.translate(bx, by); ctx.rotate(-0.38); ctx.globalAlpha = 0.9; ctx.drawImage(band, -bw / 2, -bh / 2, bw, bh); ctx.restore(); ctx.globalAlpha = 1;
    // Nebulas.
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = clamp(1.15 - z * 0.42, 0.22, 0.95); // calmer nebulas up close so faces stay readable
    CATS.forEach(c => {
      if (c.cx == null || !c.count) return;
      const [x, y] = toScreen(c.cx, c.cy), size = (c.radius * 3.4) * z;
      if (x + size < 0 || y + size < 0 || x - size > W || y - size > H) return;
      const breathe = S.motion ? 1 + 0.03 * Math.sin(t / 2200 + c.i) : 1;
      ctx.drawImage(nebulaTex(c), x - (size * breathe) / 2, y - (size * breathe) / 2, size * breathe, size * breathe);
    });
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
  }

  function drawMeteors(t, dt) {
    if (!S.motion) { R.meteors = []; return; }
    if (t > R.nextMeteor) {
      R.nextMeteor = t + 2500 + Math.random() * 4500;
      R.meteors.push({ x: Math.random() * R.W * 0.8 + R.W * 0.2, y: Math.random() * R.H * 0.4, vx: -(5 + Math.random() * 4), vy: 2.2 + Math.random() * 1.5, life: 1 });
    }
    R.meteors = R.meteors.filter(m => m.life > 0);
    R.meteors.forEach(m => {
      m.x += m.vx * dt / 16; m.y += m.vy * dt / 16; m.life -= dt / 1100;
      const g = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 14, m.y - m.vy * 14);
      g.addColorStop(0, "rgba(255,255,255," + m.life + ")"); g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.strokeStyle = g; ctx.lineWidth = 2; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(m.x - m.vx * 14, m.y - m.vy * 14); ctx.stroke();
    });
  }

  function draw(t, dt) {
    const W = R.W, H = R.H, z = R.cam.z, now = performance.now();
    drawSky(t);
    drawMeteors(t, dt);

    // Constellation threads through the brightest stars.
    ctx.lineWidth = 1;
    CATS.forEach(c => {
      const list = R.stars.filter(s => s.cat === c).slice(0, 7);
      if (list.length < 2) return;
      ctx.strokeStyle = c.color + "40"; ctx.setLineDash([2, 7]); ctx.beginPath();
      list.forEach((s, i) => { const [x, y] = toScreen(s.x, s.y); if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); });
      ctx.stroke();
    });
    ctx.setLineDash([]);

    // Constellation names, fading out as you zoom in.
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const nameAlpha = clamp(1.6 - z * 1.4, 0, 1);
    if (nameAlpha > 0.02) CATS.forEach(c => {
      if (c.cx == null || !c.count) return;
      const [x, y] = toScreen(c.cx, c.cy + c.radius + 70);
      ctx.globalAlpha = nameAlpha;
      ctx.font = "700 15px 'Space Grotesk', sans-serif"; ctx.fillStyle = c.color; ctx.fillText(c.label, x, y);
      ctx.font = "500 12px 'Space Grotesk', sans-serif"; ctx.fillStyle = "#A09CC0"; ctx.fillText(c.count + " stars", x, y + 17);
    });
    ctx.globalAlpha = 1;

    const hideId = (R.mode === "shake" || R.mode === "caught" || (R.anim && R.anim.kind === "absorb")) ? R.sel : null;
    const labels = [];
    for (const s of R.stars) {
      let [sx, sy] = toScreen(s.x, s.y);
      if (sx < -80 || sy < -80 || sx > W + 80 || sy > H + 80 || s.id === hideId) continue;
      const pop = popScale(s, now);
      if (pop <= 0) continue;
      const isSel = R.sel === s.id, isHover = R.hover === s.id, caught = !!S.codex[s.id];
      let r = Math.max(1.6, s.size * z) * pop;
      if (S.motion) {
        sy += Math.sin(t / 700 + s.phase) * r * 0.1;
        r *= 1 + 0.04 * Math.sin(t / 900 + s.phase * 2);
        if (isHover) { const k = (now - R.hoverT) / 260; if (k < 1) sy -= Math.sin(k * Math.PI) * r * 0.5; r *= 1.14; }
        if (isSel && R.mode === "browse") sy -= Math.abs(Math.sin(t / 380)) * r * 0.18;
      }
      if (r < 3.2) {
        ctx.globalAlpha = 0.95; ctx.fillStyle = s.tint;
        ctx.beginPath(); ctx.arc(sx, sy, r, 0, TAU); ctx.fill();
        if (r > 2.2 || caught) sparkle(sx, sy, r * 3.2, caught ? "#C6FF3D" : s.tint, 0.55, 0);
        ctx.globalAlpha = 1;
        continue;
      }
      const sp = sprite(s.tint, Math.min(70, Math.round(r)));
      ctx.drawImage(sp.c, sx - sp.size / 2, sy - sp.size / 2, sp.size, sp.size);
      const rk = rank(s.r.stars);
      if (rk.rings) {
        ctx.save(); ctx.translate(sx, sy); ctx.scale(1, 0.32); ctx.rotate(S.motion ? t / 4000 + s.phase : 0.3);
        ctx.strokeStyle = s.tint + "AA"; ctx.lineWidth = Math.max(1.2, r * 0.07);
        for (let k = 0; k < rk.rings; k++) { ctx.beginPath(); ctx.arc(0, 0, r * (1.55 + k * 0.3), 0, TAU); ctx.stroke(); }
        ctx.restore();
      }
      if (rk.k === "Legendary" && r > 8) {
        const a = S.motion ? t / 1600 + s.phase : 1;
        ctx.fillStyle = mix(s.tint, "#FFFFFF", 0.5); ctx.beginPath(); ctx.arc(sx + Math.cos(a) * r * 1.9, sy + Math.sin(a) * r * 0.6, Math.max(2, r * 0.16), 0, TAU); ctx.fill();
      }
      if (r >= 9) {
        const tw = S.motion ? 0.5 + 0.5 * Math.sin(t / 500 + s.phase * 3) : 0.8;
        sparkle(sx + r * 0.72, sy - r * 0.72, r * 0.42, "#FFFFFF", 0.35 + tw * 0.6, S.motion ? t / 1200 : 0);
      }
      if (caught) {
        ctx.strokeStyle = "#C6FF3D"; ctx.lineWidth = Math.max(2, r * 0.12);
        ctx.beginPath(); ctx.arc(sx, sy, r * 1.25, 0, TAU); ctx.stroke();
      }
      if (s.isNew && !caught) {
        const p = S.motion ? ((t / 1500 + s.phase) % 1) : 0.4;
        ctx.strokeStyle = "rgba(242,240,255," + (1 - p) * 0.85 + ")"; ctx.lineWidth = 1.6;
        ctx.beginPath(); ctx.arc(sx, sy, r * (1.25 + p * 1.1), 0, TAU); ctx.stroke();
      }
      if (isSel) {
        ctx.save(); ctx.translate(sx, sy); ctx.rotate(S.motion ? t / 1600 : 0);
        ctx.strokeStyle = "#F2F0FF"; ctx.lineWidth = 2; ctx.setLineDash([5, 7]);
        ctx.beginPath(); ctx.arc(0, 0, r * 1.75 + 8, 0, TAU); ctx.stroke(); ctx.setLineDash([]);
        for (let k = 0; k < 4; k++) { const a = (k * TAU) / 4; ctx.beginPath(); ctx.moveTo(Math.cos(a) * (r * 1.75 + 14), Math.sin(a) * (r * 1.75 + 14)); ctx.lineTo(Math.cos(a) * (r * 1.75 + 22), Math.sin(a) * (r * 1.75 + 22)); ctx.stroke(); }
        ctx.restore();
      }
      if (r >= 6.5) drawFace(sx, sy, r, s, t, isSel && R.mode === "aim");
      if (s.sponsor) { ctx.font = "700 12px 'Space Grotesk', sans-serif"; ctx.fillStyle = "#FFD23F"; ctx.fillText("Sponsored", sx, sy - r - 14); }
      const prio = isSel ? 4 : isHover ? 3 : caught ? 2 : r >= 16 ? 1 : 0;
      if (prio > 0) labels.push({ s: s, x: sx, y: sy + r * 1.3 + 12, prio: prio, caught: caught });
    }
    // Labels: most important first, skip any that would overlap.
    ctx.font = "500 12px 'Space Grotesk', sans-serif";
    const placed = [];
    labels.sort((a, b) => b.prio - a.prio || b.s.size - a.s.size).forEach(L => {
      const text = L.s.r.name, w = ctx.measureText(text).width + 12, box = [L.x - w / 2, L.y - 10, w, 20];
      if (placed.some(p => box[0] < p[0] + p[2] && box[0] + box[2] > p[0] && box[1] < p[1] + p[3] && box[1] + box[3] > p[1])) return;
      placed.push(box);
      ctx.fillStyle = "rgba(9,8,22,.82)"; roundRect(box[0], box[1], box[2], box[3], 10); ctx.fill();
      ctx.fillStyle = L.caught ? "#C6FF3D" : L.prio >= 3 ? "#FFFFFF" : "#D9D6EE";
      ctx.fillText(text, L.x, L.y);
    });

    drawAnim(t);
    drawParticles(dt);
  }

  function drawAnim(t) {
    const s = R.byId[R.sel];
    if (!s) return;
    const [tx, ty] = toScreen(s.x, s.y), now = performance.now(), a = R.anim;
    const size = 52;
    if (R.flash) {
      const p = (now - R.flash.t0) / 500;
      if (p < 1) { ctx.strokeStyle = R.flash.color; ctx.globalAlpha = 1 - p; ctx.lineWidth = 4 * (1 - p) + 1; ctx.beginPath(); ctx.arc(tx, ty, 20 + p * 90, 0, TAU); ctx.stroke(); ctx.globalAlpha = 1; }
      else R.flash = null;
    }
    if (!a) return;
    if (a.kind === "hold") {
      const x = R.W * 0.12, y = R.H * 0.84, bob = S.motion ? Math.sin(t / 300) * 4 : 0;
      ctx.fillStyle = "rgba(198,255,61,.12)"; ctx.beginPath(); ctx.ellipse(x, y + 34, 34, 9, 0, 0, TAU); ctx.fill();
      drawDevice(a.dev, x, y + bob, size, S.motion ? Math.sin(t / 500) * 0.12 : 0);
      return;
    }
    if (a.kind === "throw") {
      const p = Math.min(1, (now - a.t0) / 650), e = 1 - Math.pow(1 - p, 2.2);
      const x0 = R.W * 0.12, y0 = R.H * 0.84, cx = (x0 + tx) / 2, cy = Math.min(y0, ty) - R.H * 0.38;
      const x = (1 - e) * (1 - e) * x0 + 2 * (1 - e) * e * cx + e * e * tx;
      const y = (1 - e) * (1 - e) * y0 + 2 * (1 - e) * e * cy + e * e * ty;
      R.trail.push({ x: x, y: y, life: 1 });
      R.trail = R.trail.filter(p2 => (p2.life -= 0.06) > 0);
      R.trail.forEach(p2 => { ctx.globalAlpha = p2.life * 0.6; ctx.fillStyle = DEV[a.dev].color; ctx.beginPath(); ctx.arc(p2.x, p2.y, 10 * p2.life, 0, TAU); ctx.fill(); });
      ctx.globalAlpha = 1;
      drawDevice(a.dev, x, y, size * (1.25 - 0.25 * e), e * TAU * 2);
      return;
    }
    R.trail = [];
    if (a.kind === "absorb") {
      const p = Math.min(1, (now - a.t0) / 380), r = Math.max(2, s.size * R.cam.z) * (1 - p);
      const ang = p * TAU * 1.5, ox = Math.cos(ang) * 30 * (1 - p), oy = Math.sin(ang) * 30 * (1 - p);
      if (r > 1) { const sp = sprite(s.tint, Math.max(2, Math.round(r))); ctx.drawImage(sp.c, tx + ox - sp.size / 2, ty + oy - sp.size / 2, sp.size, sp.size); }
      ctx.strokeStyle = "rgba(255,255,255," + (1 - p) * 0.7 + ")"; ctx.lineWidth = 2;
      for (let k = 0; k < 6; k++) { const aa = k * TAU / 6 + p * 3; ctx.beginPath(); ctx.moveTo(tx + Math.cos(aa) * 70 * (1 - p), ty + Math.sin(aa) * 70 * (1 - p)); ctx.lineTo(tx + Math.cos(aa) * 40 * (1 - p), ty + Math.sin(aa) * 40 * (1 - p)); ctx.stroke(); }
      drawDevice(a.dev, tx, ty, size, 0, "#FFFFFF");
      return;
    }
    if (a.kind === "shake") {
      const p = Math.min(1, (now - a.t0) / 560);
      const rot = Math.sin(p * Math.PI * 3) * 0.45 * (1 - p);
      const hop = Math.sin(p * Math.PI) * 10;
      ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.ellipse(tx, ty + size * 0.62, size * 0.45 * (1 - hop / 30), 6, 0, 0, TAU); ctx.fill();
      drawDevice(a.dev, tx, ty - hop, size, rot);
      if (p < 0.6) { ctx.font = "700 20px 'Space Grotesk', sans-serif"; ctx.fillStyle = "#FFD23F"; ctx.globalAlpha = 1 - p / 0.6; for (let k = 0; k < a.k; k++) ctx.fillText("!", tx + size * 0.6 + k * 10, ty - size * 0.6 - p * 20); ctx.globalAlpha = 1; }
      return;
    }
    if (a.kind === "clicked") {
      const p = Math.min(1, (now - a.t0) / 700);
      drawDevice(a.dev, tx, ty, size * (1 + 0.15 * Math.sin(p * Math.PI)), 0, "#C6FF3D");
    }
  }

  function starPath(x, y, r) { ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } ctx.closePath(); }
  function burst(kind, wx, wy, color) {
    const n = kind === "confetti" ? 70 : 28;
    for (let i = 0; i < n; i++) {
      const ang = Math.random() * TAU, sp = kind === "confetti" ? 2 + Math.random() * 6 : 1 + Math.random() * 3;
      R.particles.push({ x: wx, y: wy, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - (kind === "confetti" ? 2.5 : 0), life: 1, kind: kind, shape: i % 3,
        color: kind === "poof" ? ["#A09CC0", "#D9D6EE", "#6E6A8E"][i % 3] : [color, "#C6FF3D", "#F2F0FF", "#FFD23F", "#FF5FA2"][i % 5], rot: Math.random() * 6 });
    }
  }
  function floatText(wx, wy, text, color) { R.particles.push({ x: wx, y: wy, vx: 0, vy: -1.1, life: 1, kind: "text", text: text, color: color }); }
  function drawParticles(dt) {
    const k = (dt || 16) / 16;
    R.particles = R.particles.filter(p => p.life > 0);
    R.particles.forEach(p => {
      p.x += (p.vx * k) / R.cam.z; p.y += (p.vy * k) / R.cam.z;
      if (p.kind === "confetti") { p.vy += 0.13 * k; p.vx *= 0.985; p.life -= 0.011 * k; p.rot += 0.18 * k; }
      else if (p.kind === "poof") { p.vx *= 0.94; p.vy *= 0.94; p.life -= 0.028 * k; }
      else { p.life -= 0.012 * k; }
      const [x, y] = toScreen(p.x, p.y);
      ctx.globalAlpha = clamp(p.life, 0, 1); ctx.fillStyle = p.color;
      if (p.kind === "confetti") {
        ctx.save(); ctx.translate(x, y); ctx.rotate(p.rot);
        if (p.shape === 0) { starPath(0, 0, 6); ctx.fill(); } else if (p.shape === 1) ctx.fillRect(-4, -2, 8, 4); else { ctx.beginPath(); ctx.arc(0, 0, 3, 0, TAU); ctx.fill(); }
        ctx.restore();
      } else if (p.kind === "poof") { ctx.beginPath(); ctx.arc(x, y, (1 - p.life) * 16 + 3, 0, TAU); ctx.fill(); }
      else { ctx.font = "700 22px 'Space Grotesk', sans-serif"; ctx.textAlign = "center"; ctx.strokeStyle = "#07070F"; ctx.lineWidth = 4; ctx.strokeText(p.text, x, y); ctx.fillText(p.text, x, y); }
    });
    ctx.globalAlpha = 1;
  }

  // ---------- Main loop ----------
  let last = performance.now();
  function frame(t) {
    requestAnimationFrame(frame);
    if (document.hidden || R.view !== "galaxy" || !R.W) return;
    const dt = Math.min(50, t - last); last = t;
    if (R.goal) {
      const k = 1 - Math.pow(0.002, dt / 1000);
      R.cam.x += (R.goal.x - R.cam.x) * k; R.cam.y += (R.goal.y - R.cam.y) * k; R.cam.z += (R.goal.z - R.cam.z) * k;
      if (Math.abs(R.goal.z - R.cam.z) < 0.002 && Math.abs(R.goal.x - R.cam.x) < 0.5 && Math.abs(R.goal.y - R.cam.y) < 0.5) { R.cam = Object.assign({}, R.goal); R.goal = null; }
    } else if (S.motion && R.mode === "browse" && !R.sel && !drag && t - R.lastInput > 6000 && t - R.introT0 > 3000) {
      R.cam.x += dt * 0.012 / R.cam.z; // slow ambient drift while idle
    }
    if (R.mode === "aim") updateMeter(dt);
    draw(t, dt);
  }

  function updateMeter(dt) {
    R.m += R.dir * dt * 0.095;
    if (R.m >= 100) { R.m = 100; R.dir = -1; }
    if (R.m <= 0) { R.m = 0; R.dir = 1; }
    const s = R.byId[R.sel];
    const zone = s ? rank(s.r.stars).zone : 30;
    const inZone = Math.abs(R.m - 50) <= zone / 2;
    const marker = $("marker"), label = $("zone-state"), btn = $("throw-btn");
    if (marker) marker.style.transform = "translateX(" + (R.m / 100) * (marker.parentNode.clientWidth - 10) + "px)";
    if (inZone !== R.inZone) {
      R.inZone = inZone;
      if (label) { label.textContent = inZone ? "In zone" : "Wait…"; label.classList.toggle("in", inZone); }
      if (btn) btn.setAttribute("aria-label", "Throw " + (R.dev ? DEV[R.dev].name : "") + ". Marker " + (inZone ? "inside" : "outside") + " the zone.");
      if (inZone) window.Sound.play("tick");
    }
  }

  // ---------- Input ----------
  const pointers = new Map();
  let drag = null, pinch = null, moved = false;
  function hitTest(sx, sy) {
    let best = null, bd = Infinity;
    const now = performance.now();
    for (const s of R.stars) {
      const pop = popScale(s, now);
      if (pop < 0.6) continue; // not visible yet during the intro
      const [x, y] = toScreen(s.x, s.y), r = Math.max(10, s.size * R.cam.z * pop + 6), d = Math.hypot(x - sx, y - sy);
      if (d < r && d < bd) { bd = d; best = s; }
    }
    return best;
  }
  canvas.addEventListener("pointerdown", e => {
    R.lastInput = performance.now();
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    moved = false;
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: R.cam.z };
      drag = null;
    } else if (R.mode === "browse") {
      const rect = canvas.getBoundingClientRect();
      // Pick the star under the cursor at press time, before the intro glide can move it away.
      const h = hitTest(e.clientX - rect.left, e.clientY - rect.top);
      drag = { sx: e.clientX, sy: e.clientY, cx: R.cam.x, cy: R.cam.y, hit: h ? h.id : null };
    }
  });
  canvas.addEventListener("pointermove", e => {
    R.lastInput = performance.now();
    const rect = canvas.getBoundingClientRect();
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      zoomAt((pinch.z * d / pinch.d) / R.cam.z, (a[0] + b[0]) / 2 - rect.left, (a[1] + b[1]) / 2 - rect.top);
      moved = true;
      return;
    }
    if (drag) {
      const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) { moved = true; canvas.classList.add("dragging"); }
      if (moved) { R.goal = null; R.cam.x = drag.cx - dx / R.cam.z; R.cam.y = drag.cy - dy / R.cam.z; }
      return;
    }
    const h = R.mode === "browse" ? hitTest(e.clientX - rect.left, e.clientY - rect.top) : null;
    const id = h ? h.id : null;
    if (id !== R.hover) { R.hover = id; R.hoverT = performance.now(); if (id) window.Sound.play("hover"); }
    canvas.classList.toggle("pointer", !!h);
  });
  const endPointer = e => {
    const rect = canvas.getBoundingClientRect();
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    canvas.classList.remove("dragging");
    if (drag && !moved && e.type === "pointerup") {
      const h = hitTest(e.clientX - rect.left, e.clientY - rect.top);
      const id = drag.hit || (h ? h.id : null);
      if (id) select(id);
    }
    drag = null;
  };
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("pointerleave", () => { R.hover = null; });
  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    R.lastInput = performance.now();
    if (R.mode !== "browse") return;
    const rect = canvas.getBoundingClientRect();
    zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - rect.left, e.clientY - rect.top);
  }, { passive: false });
  canvas.addEventListener("keydown", e => {
    R.lastInput = performance.now();
    if (R.mode !== "browse") return;
    const step = 80 / R.cam.z;
    const k = e.key;
    if (k === "ArrowLeft") R.cam.x -= step; else if (k === "ArrowRight") R.cam.x += step;
    else if (k === "ArrowUp") R.cam.y -= step; else if (k === "ArrowDown") R.cam.y += step;
    else if (k === "+" || k === "=") zoomAt(1.25, R.W / 2, R.H / 2);
    else if (k === "-") zoomAt(0.8, R.W / 2, R.H / 2);
    else if (k === "Escape") { R.sel = null; renderPanel(); }
    else return;
    R.goal = null; e.preventDefault();
  });
  $("zoom-in").onclick = () => { R.lastInput = performance.now(); zoomAt(1.3, R.W / 2, R.H / 2); };
  $("zoom-out").onclick = () => { R.lastInput = performance.now(); zoomAt(1 / 1.3, R.W / 2, R.H / 2); };
  $("recenter").onclick = () => { if (R.mode !== "browse") return; const f = fitView(); glide(f.x, f.y, f.z); };

  // Search: the accessible, keyboard-friendly way to explore.
  const search = $("search"), results = $("results");
  search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    if (!q) { results.hidden = true; results.innerHTML = ""; return; }
    const hits = R.stars.filter(s => !s.sponsor && (s.r.full_name + " " + (s.r.description || "") + " " + (s.r.topics || []).join(" ")).toLowerCase().includes(q)).slice(0, 8);
    results.innerHTML = hits.length ? hits.map(s => '<li><button type="button" data-id="' + esc(s.id) + '"><span>' + esc(s.r.name) + ' <small>' + esc(s.r.owner) + '</small></span><small>★ ' + fmt(s.r.stars) + '</small></button></li>').join("") : '<li class="muted" style="padding:8px">No star matches. Try another word.</li>';
    results.hidden = false;
  });
  results.addEventListener("click", e => {
    const b = e.target.closest("button[data-id]");
    if (!b) return;
    results.hidden = true; search.value = "";
    if (R.mode !== "browse") return;
    select(b.dataset.id);
  });

  // ---------- Game actions ----------
  function select(id) {
    if (R.mode !== "browse") return;
    const s = R.byId[id];
    if (!s) return;
    R.sel = id; R.copied = false; R.lastInput = performance.now();
    glide(s.x, s.y, Math.max(R.cam.z, 1.3));
    window.Sound.play("select");
    renderPanel();
  }

  function bestDev(rk) {
    const pref = { Legendary: ["cap", "brace", "orb", "cube"], Epic: ["brace", "orb", "cube", "cap"], Rare: ["orb", "cube", "brace", "cap"], Common: ["cube", "orb", "brace", "cap"] }[rk];
    return pref.find(k => S.inv[k] > 0) || null;
  }
  const totalDevices = () => DEV_KEYS.reduce((n, k) => n + (S.inv[k] || 0), 0);

  function startCatch() {
    const s = R.byId[R.sel];
    if (!s || s.sponsor || S.codex[s.id]) return;
    R.dev = bestDev(rank(s.r.stars).k);
    R.mode = "aim"; R.m = 0; R.dir = 1; R.pickerOpen = false; R.inZone = false;
    R.anim = R.dev ? { kind: "hold", dev: R.dev } : null;
    glide(s.x, s.y, Math.max(2.4, R.cam.z));
    window.Sound.play("lock");
    renderPanel();
    later(() => { const b = $("throw-btn"); if (b) b.focus(); }, 60);
  }

  function runAway() {
    R.timers.forEach(clearTimeout); R.timers = [];
    R.mode = "browse"; R.anim = null; R.pickerOpen = false;
    renderPanel();
  }

  // Timing matters: outside the bright zone the odds drop sharply.
  function catchChance(s, dev, hit) {
    const c = rank(s.r.stars).base + (S.seen[s.id] ? 0.15 : 0) + (dev ? DEV[dev].bonus : 0);
    return hit ? Math.min(0.98, c + 0.25) : Math.min(0.9, c) * 0.4;
  }

  function throwIt() {
    if (R.mode !== "aim" || !R.dev || S.inv[R.dev] <= 0) return;
    const s = R.byId[R.sel], n = s.r.stars, rk = rank(n);
    const hit = Math.abs(R.m - 50) <= rk.zone / 2;
    const chance = catchChance(s, R.dev, hit);
    const ok = Math.random() < chance;
    const shakes = ok ? 3 : 1 + Math.floor(Math.random() * 3);
    const dev = R.dev;
    S.inv[dev] -= 1; S.thrown += 1; save();
    R.mode = "throw"; R.anim = { kind: "throw", dev: dev, t0: performance.now() };
    window.Sound.play("throw");
    renderPanel(); renderHud();
    later(() => { R.anim = { kind: "absorb", dev: dev, t0: performance.now() }; R.flash = { t0: performance.now(), color: "#FFFFFF" }; window.Sound.play("lock"); }, 650);
    for (let k = 1; k <= shakes; k++) later(() => { R.mode = "shake"; R.shakes = k; R.anim = { kind: "shake", dev: dev, t0: performance.now(), k: k }; window.Sound.play("wobble", k); renderPanel(); }, 1050 + 650 * (k - 1));
    later(() => (ok ? caught(s, rk, hit, dev) : fled(s)), 1050 + 650 * shakes + 150);
  }

  function caught(s, rk, hit, dev) {
    const gain = rk.xp + (s.isNew ? 20 : 0) + (hit ? 10 : 0);
    const before = levelInfo(S.xp).level;
    S.xp += gain; S.catches += 1;
    S.codex[s.id] = { at: Date.now(), stage: stage(s.r.stars), name: s.r.name, full: s.r.full_name, cat: s.cat.key };
    const rewards = ["+" + gain + " XP" + (hit ? " with a perfect-timing bonus" : "") + (s.isNew ? " and a new-star bonus" : "") + "."];
    const inCat = Object.keys(S.codex).filter(id => S.codex[id].cat === s.cat.key).length;
    if (!S.badges[s.cat.key] && inCat >= BADGE_AT) { S.badges[s.cat.key] = Date.now(); S.inv.brace += 1; rewards.push(s.cat.badge + " earned for " + BADGE_AT + " catches in " + s.cat.label + ". +1 Bracket Trap."); }
    const after = levelInfo(S.xp).level;
    if (after > before) {
      S.inv.cube += 3; let extra = "+3 Commit Cubes";
      if (after % 3 === 0) { S.inv.orb += 1; extra += ", +1 Branch Orb"; }
      if (after >= 8) { S.inv.cap += 1; extra += ", +1 Release Capsule"; }
      rewards.push("Level up! You reached Lv " + after + ". " + extra + ".");
    }
    save();
    R.mode = "caught"; R.fresh = true; R.rewards = rewards; R.copied = false;
    R.anim = { kind: "clicked", dev: dev, t0: performance.now() };
    R.flash = { t0: performance.now(), color: "#C6FF3D" };
    burst("confetti", s.x, s.y, s.cat.color);
    floatText(s.x, s.y - 20 / R.cam.z, "+" + gain + " XP", "#C6FF3D");
    window.Sound.play("catch");
    if (after > before) later(() => window.Sound.play("levelUp"), 500);
    renderPanel(); renderHud();
    later(() => { R.anim = null; openDialog(); }, 750);
  }

  function fled(s) {
    R.anim = null; R.mode = "fled";
    R.flash = { t0: performance.now(), color: "#FF7A3D" };
    burst("poof", s.x, s.y);
    floatText(s.x, s.y - 20 / R.cam.z, "Escaped!", "#FF7A3D");
    window.Sound.play("escape");
    renderPanel();
  }

  function closeDialog() {
    $("scrim").hidden = true;
    const wasFresh = R.fresh;
    R.mode = "browse"; R.fresh = false; R.rewards = []; R.anim = null;
    renderPanel();
    canvas.focus();
    if (wasFresh && window.Ads && S.catches % window.Ads.interstitialEvery === 0) {
      window.Ads.nextBreak("after_catch", { pause: () => window.Sound.setEnabled(false), resume: () => window.Sound.setEnabled(S.sound) });
    }
  }

  function grantCubes(n, why) {
    S.inv.cube += n; save(); renderHud(); renderPanel();
    toast("+" + n + " Commit Cubes " + why + ".");
    window.Sound.play("sparkle");
  }

  function askForReward() {
    if (!window.Ads || !window.Ads.hasRewarded() || R.rewardAsked) return;
    R.rewardAsked = true;
    window.Ads.offerReward("refill_cubes", {
      pause: () => window.Sound.setEnabled(false),
      resume: () => window.Sound.setEnabled(S.sound),
      onOffer: show => { R.rewardShow = show; renderPanel(); },
      onReward: () => grantCubes(3, "for watching the ad"),
      done: () => { R.rewardShow = null; R.rewardAsked = false; renderPanel(); }
    });
  }

  function refillHTML() {
    askForReward();
    if (R.rewardShow) return '<button class="btn go" type="button" data-act="watch-ad">Watch a short ad for +3 Commit Cubes</button>';
    const hours = GAME.freeRefillHours || 6, wait = S.lastRefill + hours * 36e5 - Date.now();
    if (wait <= 0) return '<button class="btn go" type="button" data-act="free-refill">Claim 3 free Commit Cubes</button>';
    const h = Math.floor(wait / 36e5), m = Math.ceil((wait % 36e5) / 6e4);
    return '<p class="muted">Free cubes again in ' + h + "h " + m + "m. New scans also bring cubes.</p>";
  }

  // ---------- Panels ----------
  function miniStar(s, opts) {
    opts = opts || {};
    const c = s.tint || s.cat.color;
    return '<div class="mini-star"' + (opts.small ? ' style="width:48px;height:48px"' : "") + ">" + (opts.ring ? '<span class="r"></span>' : "") +
      '<span class="b" style="background:radial-gradient(circle at 35% 30%,#fff 0,' + mix(c, "#FFFFFF", 0.35) + " 32%," + c + " 72%," + mix(c, "#07070F", 0.45) + " 100%);box-shadow:0 0 18px " + c + '"></span>' +
      '<span class="e" style="left:36%"></span><span class="e" style="left:56%"></span></div>';
  }
  const typePill = c => '<span class="pill type" style="background:' + c.color + '">' + esc(c.label) + "</span>";

  function renderPanel() {
    const p = $("panel");
    const s = R.sel ? R.byId[R.sel] : null;
    let html = "";
    if (R.mode === "browse" && !s) html = idleHTML();
    else if (R.mode === "browse" && s && s.sponsor) html = sponsorHTML();
    else if (R.mode === "browse" && s) html = selectHTML(s);
    else if (R.mode === "aim") html = aimHTML(s);
    else if (R.mode === "throw" || R.mode === "shake") html = '<div class="card"><h2>' + (R.mode === "throw" ? esc(DEV[R.anim ? R.anim.dev : "cube"].name) + " away…" : ["", "Wobble…", "Wobble… wobble…", "Wobble… wobble… click?"][Math.min(3, R.shakes || 1)]) + "</h2></div>";
    else if (R.mode === "fled") html = fledHTML(s);
    else if (R.mode === "caught") html = s ? selectHTML(s) : idleHTML();
    p.innerHTML = html;
    if (R.mode === "aim") R.inZone = null; // force the meter label to refresh on the next frame
    $("hint").textContent = R.mode === "browse" ? "Drag to fly · scroll to zoom · click a star" : R.mode === "aim" ? "Locked on " + (s ? s.r.name : "") : "Hold steady…";
  }

  function idleHTML() {
    const counts = {};
    Object.keys(S.codex).forEach(id => { const k = S.codex[id].cat; counts[k] = (counts[k] || 0) + 1; });
    const badgeRows = CATS.filter(c => c.count).map(c => {
      const n = counts[c.key] || 0, got = !!S.badges[c.key];
      return '<div class="badge-row"><span class="badge-dot" style="' + (got ? "background:" + c.color + ";box-shadow:0 0 12px " + c.color : "border:2px dashed " + c.color + "88") + '"></span><span style="flex:1">' + esc(c.label) + '</span><span class="muted">' + Math.min(n, BADGE_AT) + "/" + BADGE_AT + "</span></div>";
    }).join("");
    const low = totalDevices() < 3;
    return '<div class="card"><h2>Every repo is a star</h2><p>Click a star to see what it is. Inspect it to read the repo, then catch it to add it to your Codex. Bigger stars have more GitHub stars; rings mark rare ones.</p>' +
      (low ? refillHTML() : "") + "</div>" +
      '<div class="card"><h3>Constellation badges</h3><p class="muted">Catch ' + BADGE_AT + " stars in a constellation to earn its badge and a Bracket Trap.</p>" + badgeRows + "</div>" +
      (CFG.sponsor ? sponsorCard() : "");
  }

  function sponsorCard() {
    const sp = CFG.sponsor;
    return '<div class="card sponsor-card"><span class="label">Sponsored</span><h3>' + esc(sp.name) + "</h3><p>" + esc(sp.description) + '</p><a class="btn" href="' + esc(sp.url) + '" target="_blank" rel="sponsored noopener">' + esc(sp.cta || "Learn more") + "</a></div>";
  }
  function sponsorHTML() {
    return sponsorCard() + '<button class="btn" type="button" data-act="deselect">Back to the galaxy</button>';
  }

  function selectHTML(s) {
    const r = s.r, n = r.stars, rk = rank(n), seen = !!S.seen[s.id], got = !!S.codex[s.id], st = stage(n);
    const next = st === 3 ? "Fully grown" : st === 1 ? "Becomes a Star at 1,000 GitHub stars" : "Becomes a Giant at 10,000 GitHub stars";
    const details = seen || got
      ? "<p>" + esc(r.description || "No description yet.") + '</p><dl class="facts"><dt>Language</dt><dd>' + esc(r.language || "Not set") + "</dd><dt>License</dt><dd>" + esc(r.license || "Not set") + "</dd><dt>Forks</dt><dd>" + fmt(r.forks) + "</dd><dt>Last push</dt><dd>" + ago(r.pushed_at) + "</dd><dt>Topics</dt><dd>" + esc((r.topics || []).join(", ") || "None") + "</dd><dt>Grows</dt><dd>" + next + "</dd></dl>"
      : '<p class="muted">Inspect this star to read the repo. Inspecting adds 15% to your catch rate.</p>';
    const actions = got
      ? '<button class="btn go" type="button" data-act="open-entry">View Codex entry</button>'
      : '<div class="row"><button class="btn ' + (seen ? "" : "outline") + '" type="button" data-act="inspect">' + (seen ? "Inspected" : "Inspect +15%") + '</button><button class="btn go" type="button" data-act="catch"' + (totalDevices() ? "" : " disabled") + ">Catch this star</button></div>" +
        '<p class="muted">Base catch rate ' + Math.round(rk.base * 100) + "%" + (seen ? ", +15% inspected" : "") + ". A device and good timing add more.</p>" + (totalDevices() ? "" : refillHTML());
    return '<div class="card" style="border-color:' + s.cat.color + '"><div class="head">' + miniStar(s, { ring: got }) + '<div style="min-width:0"><h2>' + esc(r.name) + '</h2><span class="muted">by ' + esc(r.owner) + "</span></div></div>" +
      '<div class="pills">' + typePill(s.cat) + '<span class="pill">' + rk.k + (rk.rings ? " · " + rk.rings + " ring" + (rk.rings > 1 ? "s" : "") : "") + '</span><span class="pill">' + stageName(n) + '</span><span class="pill">★ ' + fmt(n) + "</span>" + (s.isNew ? '<span class="pill">new</span>' : "") + (s.isUpd ? '<span class="pill">updated</span>' : "") + "</div>" +
      details + actions + '<a href="' + esc(safeUrl(r.url)) + '" target="_blank" rel="noopener">Open on GitHub</a></div>';
  }

  function aimHTML(s) {
    const rk = rank(s.r.stars), inPct = Math.round(catchChance(s, R.dev, true) * 100), outPct = Math.round(catchChance(s, R.dev, false) * 100);
    const picker = R.pickerOpen ? '<div class="devices" role="group" aria-label="Choose a catch device">' + DEV_KEYS.map(k =>
      '<button class="device" type="button" data-act="pick" data-dev="' + k + '" aria-pressed="' + (R.dev === k) + '"' + (S.inv[k] > 0 ? "" : " disabled") + "><b>" + DEV[k].name + "</b><small>" + S.inv[k] + " left · +" + Math.round(DEV[k].bonus * 100) + "%</small></button>").join("") + "</div>" : "";
    const zoneLeft = 50 - rk.zone / 2;
    const thrower = R.dev
      ? '<button class="throw" id="throw-btn" type="button" data-act="throw" aria-label="Throw ' + DEV[R.dev].name + '"><span class="top-line"><span>Throw</span><span class="zone-state" id="zone-state">Wait…</span></span><span class="track"><span class="zone" style="left:' + zoneLeft + "%;width:" + rk.zone + '%"></span><span class="marker" id="marker"></span></span><span class="muted">Press when the marker is inside the bright zone: ' + inPct + "% catch rate. Outside it: " + outPct + "%.</span></button>"
      : '<div class="card" style="padding:12px;border-style:dashed"><p>You are out of catch devices.</p>' + refillHTML() + "</div>";
    return '<div class="card" style="border-color:' + s.cat.color + '"><h2>Catching ' + esc(s.r.name) + "</h2>" +
      '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span>Using <b>' + (R.dev ? DEV[R.dev].name : "nothing") + "</b>" + (R.dev ? " · +" + Math.round(DEV[R.dev].bonus * 100) + "%" : "") + '</span><button class="btn" type="button" data-act="picker" aria-expanded="' + R.pickerOpen + '" style="min-height:40px">' + (R.pickerOpen ? "Done" : "Change") + "</button></div>" +
      picker + thrower + '<button class="btn" type="button" data-act="run">Back to the galaxy</button></div>';
  }

  function fledHTML(s) {
    const any = totalDevices() > 0;
    return '<div class="card" style="border-color:#FF7A3D"><h2>' + esc(s.r.name) + " broke free</h2><p>" + (any ? "It is still in range. Try again; inspecting first improves your odds." : "You are out of catch devices.") + "</p>" +
      (any ? "" : refillHTML()) +
      '<div class="row"><button class="btn go" type="button" data-act="retry"' + (any ? "" : " disabled") + '>Try again</button><button class="btn" type="button" data-act="run">Back to the galaxy</button></div></div>';
  }

  $("panel").addEventListener("click", e => {
    const b = e.target.closest("[data-act]");
    if (!b || b.disabled) return;
    const act = b.dataset.act, s = R.byId[R.sel];
    window.Sound.unlock();
    if (act === "inspect" && s) { S.seen[s.id] = Date.now(); save(); window.Sound.play("inspect"); R.flash = { t0: performance.now(), color: s.cat.color }; renderPanel(); }
    else if (act === "catch") startCatch();
    else if (act === "throw") throwIt();
    else if (act === "picker") { R.pickerOpen = !R.pickerOpen; renderPanel(); }
    else if (act === "pick") { R.dev = b.dataset.dev; R.anim = { kind: "hold", dev: R.dev }; R.pickerOpen = false; renderPanel(); }
    else if (act === "run") { runAway(); }
    else if (act === "retry") { R.mode = "browse"; startCatch(); }
    else if (act === "open-entry") { R.mode = "caught"; R.fresh = false; R.rewards = []; renderPanel(); openDialog(); }
    else if (act === "deselect") { R.sel = null; renderPanel(); }
    else if (act === "watch-ad" && R.rewardShow) { const show = R.rewardShow; R.rewardShow = null; show(); }
    else if (act === "free-refill") { S.lastRefill = Date.now(); grantCubes(3, "from your free refill"); }
  });

  // ---------- Caught / Codex entry dialog ----------
  function openDialog() {
    const s = R.byId[R.sel];
    if (!s) return;
    const r = s.r, rk = rank(r.stars), url = safeUrl(r.url);
    const install = "git clone " + (url === "#" ? r.full_name : url + ".git");
    const shareText = "I just caught " + r.full_name + " (" + rk.k + ", ★" + fmt(r.stars) + ") on Star Catcher!";
    const entry = S.codex[s.id];
    const grew = entry && stage(r.stars) > (entry.stage || 1);
    $("dialog").style.border = "1px solid " + s.cat.color;
    $("dialog").innerHTML =
      '<button class="close" type="button" data-act="close" aria-label="Close">×</button>' +
      '<div class="title" id="dialog-title">' + (R.fresh ? "Caught!" : "Codex entry") + "</div>" +
      (R.fresh && R.rewards.length ? '<div class="rewards">' + R.rewards.map(t => "<div>" + esc(t) + "</div>").join("") + "</div>" : "") +
      (grew ? '<div class="rewards">This star grew into a ' + stageName(r.stars) + " since you caught it.</div>" : "") +
      '<div class="head">' + miniStar(s, { ring: true }) + '<div style="min-width:0"><h2 style="margin:0;font-size:26px;overflow-wrap:anywhere">' + esc(r.name) + '</h2><span class="muted">by ' + esc(r.owner) + '</span><div class="pills" style="margin-top:6px">' + typePill(s.cat) + '<span class="pill">' + rk.k + '</span><span class="pill">' + stageName(r.stars) + "</span></div></div></div>" +
      "<p style=\"margin:0;line-height:1.5;color:#D9D6EE\">" + esc(r.description || "No description yet.") + "</p>" +
      '<div class="stats"><div><b>★ ' + fmt(r.stars) + "</b><span>stars</span></div><div><b>" + fmt(r.forks) + "</b><span>forks</span></div><div><b>" + esc(r.language || "—") + "</b><span>language</span></div><div><b>" + ago(r.pushed_at) + "</b><span>last push</span></div></div>" +
      '<div class="install"><code>' + esc(install) + '</code><button class="btn" type="button" data-act="copy" style="min-height:40px">' + (R.copied ? "Copied" : "Copy") + "</button></div>" +
      '<p class="muted" style="margin:0">Update alerts are on: each 6-hour scan shows new releases, star growth and when this star grows to its next stage.</p>' +
      '<div style="display:flex;flex-wrap:wrap;gap:10px"><button class="btn go" type="button" data-act="close">Keep exploring</button><a class="btn" href="' + esc(url) + '" target="_blank" rel="noopener">Open on GitHub</a><a class="btn" href="https://twitter.com/intent/tweet?text=' + encodeURIComponent(shareText) + "&url=" + encodeURIComponent(location.origin + location.pathname) + '" target="_blank" rel="noopener">Share</a></div>';
    $("scrim").hidden = false;
    $("dialog").focus();
    if (entry && grew) { entry.stage = stage(r.stars); save(); }
  }
  $("scrim").addEventListener("click", e => {
    if (e.target === $("scrim")) return closeDialog();
    const b = e.target.closest("[data-act]");
    if (!b) return;
    if (b.dataset.act === "close") closeDialog();
    if (b.dataset.act === "copy") {
      const code = $("dialog").querySelector("code");
      try { navigator.clipboard.writeText(code.textContent).catch(() => {}); } catch (err) { /* ignore */ }
      R.copied = true; b.textContent = "Copied";
    }
  });
  $("scrim").addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); closeDialog(); }
    if (e.key === "Tab") { // keep focus inside the dialog
      const f = [...$("dialog").querySelectorAll("button,a[href]")];
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  });

  // ---------- HUD, views, toast ----------
  function renderHud() {
    $("inv").innerHTML = DEV_KEYS.map(k => '<span class="chip" title="' + DEV[k].name + '"><span class="dot" style="background:' + DEV[k].color + ";border-radius:" + (k === "orb" ? "50%" : k === "cap" ? "6px" : "3px") + '"></span>' + S.inv[k] + '<span class="sr-only"> ' + DEV[k].name + "</span></span>").join("");
    const li = levelInfo(S.xp);
    $("lvl").textContent = li.level;
    $("xpfill").style.width = Math.round((li.into / li.need) * 100) + "%";
    $("level-chip").title = li.into + " / " + li.need + " XP to next level";
    $("sound-btn").textContent = S.sound ? "Sound on" : "Sound off";
    $("sound-btn").setAttribute("aria-pressed", String(S.sound));
    $("motion-btn").textContent = S.motion ? "Motion on" : "Motion off";
    $("motion-btn").setAttribute("aria-pressed", String(!S.motion));
  }
  $("sound-btn").onclick = () => { S.sound = !S.sound; window.Sound.setEnabled(S.sound); if (window.Ads) window.Ads.setSound(S.sound); save(); renderHud(); window.Sound.play("select"); };
  $("motion-btn").onclick = () => { S.motion = !S.motion; save(); renderHud(); };

  let toastTimer = null;
  function toast(text) {
    const el = $("toast");
    el.textContent = text; el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 5000);
  }

  document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => setView(t.dataset.view)));
  function setView(v) {
    if (R.mode === "throw" || R.mode === "shake") return;
    if (R.mode === "aim" && v !== "galaxy") runAway();
    R.view = v;
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-pressed", String(t.dataset.view === v)));
    $("view-galaxy").hidden = v !== "galaxy";
    $("view-codex").hidden = v !== "codex";
    $("view-card").hidden = v !== "card";
    if (v === "codex") renderCodex();
    if (v === "card") renderCard();
    if (v === "galaxy") resize();
  }

  function caughtStars() {
    return Object.keys(S.codex).map(id => R.byId[id]).filter(Boolean);
  }

  function renderCodex() {
    const list = caughtStars().sort((a, b) => S.codex[b.id].at - S.codex[a.id].at);
    $("codex-count").textContent = list.length + " caught · " + Object.keys(S.seen).length + " inspected · " + R.stars.filter(s => !s.sponsor).length + " stars charted";
    $("codex-grid").innerHTML = list.length ? list.map(s => {
      const grew = stage(s.r.stars) > (S.codex[s.id].stage || 1);
      return '<button class="entry" type="button" data-id="' + esc(s.id) + '" style="border-color:' + s.cat.color + '">' + miniStar(s, { ring: true }) + "<b>" + esc(s.r.name) + '</b><span class="muted">' + esc(s.cat.label) + " · " + stageName(s.r.stars) + " · ★ " + fmt(s.r.stars) + '</span><span class="muted">' + (grew ? "Grew since you caught it" : "Caught " + ago(S.codex[s.id].at)) + "</span></button>";
    }).join("") : '<div class="empty">Your Codex is empty. Head to the galaxy, click a star and catch it.<br><br><button class="btn go" type="button" data-go="galaxy">Go to the galaxy</button></div>';
  }
  $("codex-grid").addEventListener("click", e => {
    if (e.target.closest("[data-go]")) return setView("galaxy");
    const b = e.target.closest("[data-id]");
    if (!b) return;
    setView("galaxy");
    R.sel = b.dataset.id; R.mode = "caught"; R.fresh = false; R.rewards = [];
    const s = R.byId[R.sel];
    glide(s.x, s.y, Math.max(R.cam.z, 1.4));
    renderPanel(); openDialog();
  });

  function renderCard() {
    const list = caughtStars().sort((a, b) => b.r.stars - a.r.stars), li = levelInfo(S.xp);
    const team = [0, 1, 2, 3, 4, 5].map(i => list[i] ? "<div>" + miniStar(list[i], { small: true }) + esc(list[i].r.name) + "</div>" : '<div style="color:#A09CC0"><div class="mini-star" style="width:48px;height:48px"><span class="b" style="border:2px dashed #3A3A58"></span></div>open slot</div>').join("");
    const badges = CATS.map(c => '<span class="badge-row" style="font-size:14px"><span class="badge-dot" style="' + (S.badges[c.key] ? "background:" + c.color : "border:2px dashed " + c.color + "88") + '"></span>' + esc(c.badge) + "</span>").join("");
    const badgeCount = Object.keys(S.badges).length;
    const share = S.trainer + " has caught " + list.length + " Claude repos on Star Catcher: Lv " + li.level + ", " + badgeCount + "/" + CATS.length + " badges. Brightest catch: " + (list[0] ? list[0].r.full_name : "still searching") + ".";
    $("explorer").innerHTML =
      '<div class="explorer-card"><div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><div style="flex:1;min-width:220px"><label for="tname" class="muted">Explorer name</label><input id="tname" class="name-input" maxlength="20" value="' + esc(S.trainer) + '"></div>' +
      '<div class="statline" style="flex:1;min-width:260px"><div><b>' + li.level + '</b><span>level</span></div><div><b>' + list.length + '</b><span>caught</span></div><div><b>' + S.thrown + '</b><span>thrown</span></div><div><b>' + badgeCount + "</b><span>badges</span></div></div></div>" +
      '<b>Brightest catches</b><div class="team">' + team + "</div><b>Constellation badges</b><div style=\"display:flex;flex-wrap:wrap;gap:14px\">" + badges + "</div></div>" +
      '<div class="card" style="flex:1 1 300px;max-width:420px"><h3>Share your sky</h3><p id="share-text">' + esc(share) + '</p><button class="btn go" type="button" id="copy-share">Copy share text</button><a class="btn" target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?text=' + encodeURIComponent(share) + "&url=" + encodeURIComponent(location.origin + location.pathname) + '">Post on X</a><p class="muted">Progress is saved in this browser.</p></div>';
    $("tname").addEventListener("change", e => { S.trainer = e.target.value.trim().slice(0, 20) || "Explorer"; save(); renderCard(); });
    $("copy-share").onclick = e => { try { navigator.clipboard.writeText(share).catch(() => {}); } catch (err) { /* ignore */ } e.target.textContent = "Copied"; };
  }

  // ---------- Boot ----------
  // Links like ?star=owner/repo (from the repo pages, badges and social posts) open that star.
  function deepLink() {
    try { return (new URLSearchParams(location.search).get("star") || "").trim().toLowerCase(); } catch (e) { return ""; }
  }
  function openDeepLink() {
    const want = deepLink();
    if (!want) return;
    const s = R.stars.find(x => x.r && x.r.full_name && x.r.full_name.toLowerCase() === want);
    if (s) later(() => { if (R.mode === "browse") select(s.id); }, S.motion ? 1500 : 50);
  }
  function analytics() {
    const gc = CFG.analytics && CFG.analytics.goatcounter;
    if (!gc) return;
    const sc = document.createElement("script");
    sc.async = true; sc.src = "https://gc.zgo.at/count.js"; sc.setAttribute("data-goatcounter", "https://" + gc + ".goatcounter.com/count");
    document.head.appendChild(sc);
  }
  function applyLinks() {
    const L = CFG.links || {};
    if (L.support) { $("support-link").href = L.support; $("support-link").hidden = false; }
    if (L.newsletter) { $("newsletter-link").href = L.newsletter; $("newsletter").hidden = false; }
    if (L.source) $("source-link").href = L.source;
  }

  function onData(data) {
    R.data = data;
    if (!R.W) resize();
    build(data);
    const repos = data.repos || [];
    // A new 6-hour scan since the last visit: reward the return and report growth.
    if (data.last_updated && S.lastData && S.lastData !== data.last_updated) {
      const since = new Date(S.lastData).getTime();
      const fresh = repos.filter(r => r.first_seen && new Date(r.first_seen).getTime() > since).length;
      const grown = caughtStars().filter(s => stage(s.r.stars) > (S.codex[s.id].stage || 1)).map(s => s.r.name);
      S.inv.cube += 3;
      toast("New scan: " + fresh + " new star" + (fresh === 1 ? "" : "s") + " appeared. +3 Commit Cubes." + (grown.length ? " Grew: " + grown.slice(0, 3).join(", ") + "." : ""));
      window.Sound.play("sparkle");
    }
    if (data.last_updated) S.lastData = data.last_updated;
    if (!S.lastRefill) S.lastRefill = Date.now();
    save();
    $("data-note").textContent = (data.sample ? "Sample data until the first scan runs. " : "") + R.stars.filter(s => !s.sponsor).length + " stars charted" + (data.total ? " of " + data.total + " repos" : "") + " · last scan " + ago(data.last_updated);
    renderHud(); renderPanel();
    openDeepLink();
  }

  applyLinks();
  analytics();
  window.Sound.setEnabled(S.sound);
  if (window.Ads) window.Ads.init();
  renderHud(); renderPanel();
  resize();
  requestAnimationFrame(frame);
  fetch("data/repos.json?v=" + Math.floor(Date.now() / 36e5), { cache: "no-cache" })
    .then(r => r.json())
    .then(onData)
    .catch(() => { $("data-note").textContent = "Could not load the galaxy data. Run the “Update repo data” workflow once."; });
})();
