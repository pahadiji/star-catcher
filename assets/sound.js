/*
 * Star Catcher — tiny sound engine.
 * Every sound is synthesized with the Web Audio API, so there are no audio
 * files to license or download. Sound stays off until the player turns it on
 * or interacts with the page (browsers block autoplay anyway).
 */
(function () {
  let ctx = null;
  let master = null;
  let enabled = false;

  function ensure() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0.35;
      master.connect(ctx.destination);
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  // One soft "blip": an oscillator with a quick attack and exponential release.
  function tone(freq, start, dur, type, vol, slideTo) {
    const c = ensure();
    if (!c || !enabled) return;
    const t = c.currentTime + start;
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = type || "sine";
    o.frequency.setValueAtTime(freq, t);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol || 0.4, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g);
    g.connect(master);
    o.start(t);
    o.stop(t + dur + 0.02);
  }

  // Filtered noise, for whooshes and poofs.
  function noise(start, dur, fromHz, toHz, vol) {
    const c = ensure();
    if (!c || !enabled) return;
    const t = c.currentTime + start;
    const len = Math.max(1, Math.floor(c.sampleRate * dur));
    const buf = c.createBuffer(1, len, c.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    const src = c.createBufferSource();
    src.buffer = buf;
    const f = c.createBiquadFilter();
    f.type = "bandpass";
    f.Q.value = 1.2;
    f.frequency.setValueAtTime(fromHz, t);
    f.frequency.exponentialRampToValueAtTime(toHz, t + dur);
    const g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol || 0.3, t + 0.03);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f);
    f.connect(g);
    g.connect(master);
    src.start(t);
    src.stop(t + dur + 0.02);
  }

  const NOTES = { C5: 523.25, D5: 587.33, E5: 659.25, G5: 783.99, A5: 880, C6: 1046.5, E6: 1318.5, G6: 1568 };

  const SFX = {
    hover() { tone(1400, 0, 0.05, "sine", 0.06); },
    select() { tone(NOTES.E5, 0, 0.09, "triangle", 0.25); tone(NOTES.A5, 0.06, 0.12, "triangle", 0.22); },
    inspect() { [NOTES.C6, NOTES.E6, NOTES.G6].forEach((f, i) => tone(f, i * 0.05, 0.12, "sine", 0.15)); },
    lock() { tone(220, 0, 0.18, "sawtooth", 0.08, 440); tone(NOTES.C5, 0.12, 0.1, "square", 0.08); },
    tick() { tone(1800, 0, 0.02, "square", 0.03); },
    throw() { noise(0, 0.5, 400, 3200, 0.25); tone(300, 0, 0.45, "sine", 0.12, 900); },
    wobble(n) { const base = [392, 440, 494][Math.min(2, (n || 1) - 1)]; tone(base, 0, 0.16, "triangle", 0.3, base * 0.8); },
    catch() { [NOTES.C5, NOTES.E5, NOTES.G5, NOTES.C6].forEach((f, i) => tone(f, i * 0.09, 0.22, "triangle", 0.3)); tone(NOTES.E6, 0.38, 0.4, "sine", 0.2); },
    escape() { noise(0, 0.35, 2400, 300, 0.3); tone(660, 0, 0.3, "square", 0.08, 160); },
    levelUp() { [NOTES.C5, NOTES.G5, NOTES.C6, NOTES.E6, NOTES.G6].forEach((f, i) => tone(f, i * 0.08, 0.3, "square", 0.12)); },
    sparkle() { [NOTES.G6, NOTES.E6, NOTES.C6, NOTES.G6].forEach((f, i) => tone(f, i * 0.06, 0.1, "sine", 0.12)); },
    error() { tone(200, 0, 0.18, "square", 0.1, 140); }
  };

  window.Sound = {
    play(name, arg) { try { if (enabled && SFX[name]) SFX[name](arg); } catch (e) { /* audio is optional */ } },
    setEnabled(on) { enabled = !!on; if (on) ensure(); },
    isEnabled() { return enabled; },
    unlock() { ensure(); }
  };
})();
