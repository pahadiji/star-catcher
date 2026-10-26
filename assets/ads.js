/*
 * Star Catcher — ads wrapper.
 * - Google H5 Games Ads (Ad Placement API) for rewarded ads and "next" interstitials.
 * - One display network (AdSense, Carbon or EthicalAds) for the sidebar and footer slots.
 * Everything is driven by window.SITE_CONFIG.ads, and every call is safe when ads are off.
 */
(function () {
  const cfg = (window.SITE_CONFIG && window.SITE_CONFIG.ads) || {};
  const h5 = cfg.h5 || {};
  const display = cfg.display || {};
  let h5Ready = false;

  function loadScript(src, attrs) {
    const s = document.createElement("script");
    s.async = true;
    s.src = src;
    Object.keys(attrs || {}).forEach(k => s.setAttribute(k, attrs[k]));
    document.head.appendChild(s);
    return s;
  }

  // ---- H5 Games Ads (Ad Placement API) ----
  function initH5() {
    if (!h5.enabled || !h5.client || h5.client.indexOf("XXXX") >= 0) return;
    const attrs = { "data-ad-client": h5.client, crossorigin: "anonymous" };
    if (h5.testMode) attrs["data-adbreak-test"] = "on";
    attrs["data-ad-frequency-hint"] = "60s";
    loadScript("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + encodeURIComponent(h5.client), attrs);
    window.adsbygoogle = window.adsbygoogle || [];
    window.adBreak = window.adConfig = function (o) { window.adsbygoogle.push(o); };
    window.adConfig({ preloadAdBreaks: "on", sound: window.Sound && window.Sound.isEnabled() ? "on" : "off" });
    h5Ready = true;
  }

  /*
   * Ask the API whether a rewarded ad is available.
   * onOffer(showFn) is called only when an ad can actually be shown; the game then
   * shows its own "Watch an ad for +3 cubes" button and calls showFn() on click.
   * onReward() runs only if the player watched to the end.
   */
  function offerReward(name, hooks) {
    if (!h5Ready) return false;
    let viewed = false;
    window.adBreak({
      type: "reward",
      name: name,
      beforeAd: () => hooks.pause && hooks.pause(),
      afterAd: () => hooks.resume && hooks.resume(),
      beforeReward: showAdFn => hooks.onOffer && hooks.onOffer(showAdFn),
      adViewed: () => { viewed = true; },
      adDismissed: () => { viewed = false; },
      adBreakDone: () => { if (viewed && hooks.onReward) hooks.onReward(); if (hooks.done) hooks.done(); }
    });
    return true;
  }

  // A full-screen break at a natural transition (after closing a catch card).
  function nextBreak(name, hooks) {
    if (!h5Ready) { if (hooks && hooks.done) hooks.done(); return; }
    window.adBreak({
      type: "next",
      name: name,
      beforeAd: () => hooks && hooks.pause && hooks.pause(),
      afterAd: () => hooks && hooks.resume && hooks.resume(),
      adBreakDone: () => hooks && hooks.done && hooks.done()
    });
  }

  function setSound(on) { if (h5Ready) window.adConfig({ sound: on ? "on" : "off" }); }

  // ---- Display slots ----
  function fillSlot(el, which) {
    if (!el) return;
    const type = display.type || "none";
    if (type === "none") { el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = "";
    const label = document.createElement("span");
    label.className = "ad-label";
    label.textContent = "Advertisement";
    el.appendChild(label);
    if (type === "adsense") {
      if (!document.querySelector('script[src*="adsbygoogle.js"]')) {
        loadScript("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + encodeURIComponent(display.adsenseClient), { crossorigin: "anonymous" });
      }
      const ins = document.createElement("ins");
      ins.className = "adsbygoogle";
      ins.style.display = "block";
      ins.setAttribute("data-ad-client", display.adsenseClient);
      ins.setAttribute("data-ad-slot", which === "footer" ? display.adsenseFooterSlot : display.adsenseSidebarSlot);
      ins.setAttribute("data-ad-format", "auto");
      ins.setAttribute("data-full-width-responsive", "true");
      el.appendChild(ins);
      try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) { /* blocked */ }
    } else if (type === "carbon" && which === "sidebar") {
      // Carbon allows one unit per page, so only the sidebar slot uses it.
      const s = document.createElement("script");
      s.async = true;
      s.id = "_carbonads_js";
      s.src = "https://cdn.carbonads.com/carbon.js?serve=" + encodeURIComponent(display.carbonServe) + "&placement=" + encodeURIComponent(display.carbonPlacement);
      el.appendChild(s);
    } else if (type === "ethicalads" && which === "sidebar") {
      if (!document.querySelector('script[src*="ethicalads"]')) loadScript("https://media.ethicalads.io/media/client/ethicalads.min.js", {});
      const d = document.createElement("div");
      d.setAttribute("data-ea-publisher", display.ethicalPublisher);
      d.setAttribute("data-ea-type", "image");
      el.appendChild(d);
    } else {
      el.hidden = true;
    }
  }

  window.Ads = {
    init() {
      initH5();
      fillSlot(document.getElementById("ad-sidebar"), "sidebar");
      fillSlot(document.getElementById("ad-footer"), "footer");
    },
    hasRewarded() { return h5Ready; },
    offerReward: offerReward,
    nextBreak: nextBreak,
    setSound: setSound,
    interstitialEvery: h5.interstitialEvery || 3
  };
})();
