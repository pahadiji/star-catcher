/*
 * Star Catcher — site configuration.
 * Edit this file to switch ads on, add a sponsor, and set your links.
 * Everything here is safe to commit: it contains no secrets.
 */
window.SITE_CONFIG = {
  siteName: "Star Catcher",
  tagline: "Explore every Claude repo on GitHub as a galaxy. Catch the stars you like.",

  // ---------- Ads ----------
  ads: {
    // 1) Google H5 Games Ads (Ad Placement API): rewarded + "next" interstitials.
    //    Apply at https://support.google.com/adsense/answer/9959170 then set your client id.
    h5: {
      enabled: false,
      client: "ca-pub-XXXXXXXXXXXXXXXX",
      testMode: true,            // keep true until Google approves the site
      interstitialEvery: 3       // show a "next" break after every N catches (never mid-throw)
    },

    // 2) One display unit in the sidebar and one in the footer.
    //    type: "none" | "adsense" | "carbon" | "ethicalads"
    display: {
      type: "none",
      adsenseClient: "ca-pub-XXXXXXXXXXXXXXXX",
      adsenseSidebarSlot: "0000000000",
      adsenseFooterSlot: "0000000000",
      carbonServe: "XXXXXXXX",          // from your Carbon dashboard script src (?serve=...)
      carbonPlacement: "yourdomaincom",
      ethicalPublisher: "your-publisher-id"
    }
  },

  // ---------- Sponsored star (sold directly, clearly labelled) ----------
  // Set to null to hide. Shown as a golden star in the centre of the galaxy.
  sponsor: {
    name: "Your tool here",
    url: "mailto:you@example.com?subject=Sponsor%20Star%20Catcher",
    description: "Put your AI developer tool in the centre of the galaxy. Every explorer sees it.",
    cta: "Become the sponsored star"
  },

  // ---------- Links ----------
  links: {
    newsletter: "",           // e.g. your Beehiiv/Substack signup URL; empty hides the box
    support: "",              // Buy Me a Coffee / GitHub Sponsors URL; empty hides the button
    sponsorEmail: "you@example.com",
    source: "https://github.com/YOURNAME/star-catcher"
  },

  // ---------- Game tuning ----------
  game: {
    startDevices: { cube: 10, orb: 3, brace: 1, cap: 0 },
    maxStarsOnMap: 700,       // biggest repos + every new one
    freeRefillHours: 6        // free +3 cubes every N hours when no rewarded ad is available
  }
};
