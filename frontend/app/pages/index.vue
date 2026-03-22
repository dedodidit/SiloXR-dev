<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../constants/site"

useHead({
  title: "Stop Losing Sales to Stockouts | SiloXR — The Business Decision Engine",
  link: [
    { rel: 'canonical', href: 'https://siloxr.com' }
  ],
  meta: [
    { name: "description",
      content: "Stop losing money on out-of-stock items and wasted inventory. SiloXR predicts your stock risks and tells you exactly what to reorder before you lose a sale. Free for small businesses." },
    { name: "keywords",
      content: "inventory management for small business, avoid stockouts, stock prediction software, retail inventory alerts, reorder alerts system, demand forecasting retail" },
    
    /* Open Graph / Facebook */
    { property: "og:type",        content: "website" },
    { property: "og:title",       content: "Stop Losing Sales to Stockouts | SiloXR" },
    { property: "og:description", content: "Predict stockouts before they happen. See your revenue at risk and get clear reorder alerts automatically." },
    { property: "og:image",       content: "/og-image.png" },
    
    /* Twitter */
    { name: "twitter:card",        content: "summary_large_image" },
    { name: "twitter:title",       content: "SiloXR — Know what your business needs before it happens" },
    { name: "twitter:description", content: "The decision engine that prevents stockouts and reduces waste for small retail businesses." },
    { name: "twitter:image",       content: "/og-image.png" },
  ]
})

const features = [
  { icon: "📉", title: "Stop losing sales",       desc: "Predict exactly when stock hits zero. Know days in advance so you never turn a customer away." },
  { icon: "💰", title: "Protect your cash flow",  desc: "Don't tie up money in slow-movers. Our AI tells you what to hold and what to restock now." },
  { icon: "⚡", title: "Fix messy data",          desc: "No perfect spreadsheets required. We turn your existing receipts and logs into clear profit-saving actions." },
  { icon: "📡", title: "Works without internet",   desc: "Record sales and stock counts in the shop, offline. We sync and analyze when you're back online." },
  { icon: "📲", title: "Instant profit alerts",   desc: "Get WhatsApp and email alerts the moment a product enters the 'Risk Zone' for lost revenue." },
  { icon: "🧠", title: "Smarter every day",       desc: "The more sales you log, the more accurate your reorder points become, eliminating guesswork." },
]

const industries = [
  { name: "Retail & FMCG",        icon: "🏪" },
  { name: "Food & Beverage",       icon: "🥤" },
  { name: "Pharmacies",            icon: "💊" },
  { name: "Wholesale & Distribution",icon: "📦" },
  { name: "Mini-Supermarkets",     icon: "🛒" },
  { name: "Hardware & Tools",      icon: "🔧" },
]

const steps = [
  { n: "01", title: "Connect your stock",    desc: "Upload your current list via CSV, Excel, or even a photo of a stock sheet." },
  { n: "02", title: "Log a few sales",       desc: "Record sales as they happen. It takes seconds on your phone, even without internet." },
  { n: "03", title: "See your risk",         desc: "SiloXR immediately identifies which products are trending toward a stockout." },
  { n: "04", title: "Take action",           desc: "Get a clear 'Restock' or 'Hold' list every morning to maximize your daily profit." },
]
</script>

<template>
  <div class="landing">

    <nav class="landing__nav">
      <div class="landing__nav-inner">
        <div class="landing__brand">
          <div class="landing__brand-mark" aria-hidden="true">
            <svg viewBox="0 0 12 12" fill="none" width="12" height="12">
              <path d="M2 9L6 3L10 9H2Z" fill="white" opacity=".9"/>
              <path d="M4 9L6 6L8 9H4Z" fill="white" opacity=".5"/>
            </svg>
          </div>
          SiloXR
        </div>
        <div class="landing__nav-links">
          <a href="#how-it-works" class="landing__nav-link">How it works</a>
          <a href="#industries"   class="landing__nav-link">Industries</a>
          <NuxtLink to="/auth/login"  class="landing__nav-link">Sign in</NuxtLink>
          <NuxtLink to="/auth/signup" class="btn btn-primary btn-sm">Start Free — See Risk</NuxtLink>
        </div>
      </div>
    </nav>

    <section class="landing__hero">
      <div class="landing__hero-inner">
        <div class="landing__eyebrow">Inventory Intelligence</div>
        <h1 class="landing__headline">
          Stop losing sales to stockouts<br/>
          <span class="landing__headline-accent">before they happen</span>
        </h1>
        <p class="landing__sub">
          Most small businesses lose 15% of their revenue to out-of-stock items. 
          SiloXR predicts your stock risks and tells you exactly what to reorder 
          to keep your profit growing—even with messy data.
        </p>
        <div class="landing__hero-ctas">
          <NuxtLink to="/auth/signup" class="btn btn-primary btn-lg">
            Check your stock risk — It's free
          </NuxtLink>
          <a href="/api/v1/upload/sample/" class="btn btn-secondary btn-lg" target="_blank">
            See sample reorder report
          </a>
        </div>
        <p class="landing__hero-fine">
          Free for up to 5 products. Setup takes 2 minutes. No credit card required.
        </p>
      </div>

      <div class="landing__hero-card surface-raised">
        <div class="landing__mock-strip" style="background: #E53E3E" />
        <div class="landing__mock-body">
          <div class="landing__mock-sku">SKU: PALM-OIL-5L</div>
          <div class="landing__mock-action" style="color: #E53E3E">RESTOCK IMMEDIATELY</div>
          <div class="landing__mock-reason">
            <strong>₦12,400 at risk this week.</strong> Current stock will run out in ~2 days. Demand is spiking 15% above normal.
          </div>
          <div class="landing__mock-conf">
            <div class="landing__mock-bar">
              <div class="landing__mock-fill" style="width:94%; background: #E53E3E" />
            </div>
            <span class="landing__mock-pct" style="color:#E53E3E">94% Risk</span>
          </div>
        </div>
      </div>
    </section>

    <section class="landing__features" style="background: var(--bg); border-top: none;">
      <h2 class="landing__section-title">You are losing money every day if...</h2>
      <div class="landing__features-grid">
        <div class="landing__feature-card surface" style="border-left: 3px solid #E53E3E">
          <h3 class="landing__feature-title">Customers leave empty-handed</h3>
          <p class="landing__feature-desc">You only realize you're out of a best-seller when a customer asks for it. That's money walking out the door.</p>
        </div>
        <div class="landing__feature-card surface" style="border-left: 3px solid #E53E3E">
          <h3 class="landing__feature-title">Your cash is tied up in "dust"</h3>
          <p class="landing__feature-desc">You overstocked items that aren't moving, leaving you without the cash to buy what's actually selling.</p>
        </div>
        <div class="landing__feature-card surface" style="border-left: 3px solid #E53E3E">
          <h3 class="landing__feature-title">You rely on "gut feeling"</h3>
          <p class="landing__feature-desc">Manual stock counts are slow and prone to error. One bad reorder can wipe out your month's profit.</p>
        </div>
      </div>
    </section>

    <section class="landing__features">
      <h2 class="landing__section-title">Everything you need to protect your profit.</h2>
      <div class="landing__features-grid">
        <div v-for="f in features" :key="f.title" class="landing__feature-card surface">
          <span class="landing__feature-icon">{{ f.icon }}</span>
          <h3 class="landing__feature-title">{{ f.title }}</h3>
          <p class="landing__feature-desc">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <section class="landing__how" style="background: var(--bg-card); border-bottom: 1px solid var(--border-subtle);">
      <div class="landing__how-inner">
        <h2 class="landing__section-title">Why smart operators choose SiloXR</h2>
        <div class="landing__steps">
          <div class="landing__step">
            <div class="landing__step-num">✓</div>
            <div>
              <h3 class="landing__step-title">Zero Data Perfection Required</h3>
              <p class="landing__step-desc">Most software fails because your data is messy. SiloXR is designed to find patterns in the chaos.</p>
            </div>
          </div>
          <div class="landing__step">
            <div class="landing__step-num">✓</div>
            <div>
              <h3 class="landing__step-title">Built for the Shop Floor</h3>
              <p class="landing__step-desc">Fast, offline-first mobile interface. Record sales in the middle of a rush without breaking a sweat.</p>
            </div>
          </div>
          <div class="landing__step">
            <div class="landing__step-num">✓</div>
            <div>
              <h3 class="landing__step-title">Focus on the Bottom Line</h3>
              <p class="landing__step-desc">We don't just give you charts. We give you a daily to-do list that directly saves you money.</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="landing__how" id="how-it-works">
      <div class="landing__how-inner">
        <h2 class="landing__section-title">Get your first reorder alert in under 10 minutes</h2>
        <div class="landing__steps">
          <div v-for="s in steps" :key="s.n" class="landing__step">
            <div class="landing__step-num">{{ s.n }}</div>
            <div>
              <h3 class="landing__step-title">{{ s.title }}</h3>
              <p class="landing__step-desc">{{ s.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="landing__upload surface">
      <div class="landing__upload-inner">
        <div>
          <h2 class="landing__upload-title">Already have a stock list?</h2>
          <p class="landing__upload-desc">
            Stop manually typing. Upload your existing CSV, Excel, or a PDF. 
            We'll identify your high-risk products in seconds.
          </p>
          <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
            <NuxtLink to="/auth/signup" class="btn btn-primary">
              Import and Check Risk
            </NuxtLink>
            <a href="/api/v1/upload/sample/" class="btn btn-secondary" target="_blank">
              Download Sample Template
            </a>
          </div>
        </div>
        <div class="landing__upload-formats">
          <span class="landing__format-badge">CSV</span>
          <span class="landing__format-badge">Excel</span>
          <span class="landing__format-badge">PDF</span>
        </div>
      </div>
    </section>

    <section class="landing__industries" id="industries">
      <h2 class="landing__section-title">Built for businesses that cannot afford stock mistakes</h2>
      <div class="landing__ind-grid">
        <div v-for="ind in industries" :key="ind.name" class="landing__ind-card surface">
          <span class="landing__ind-icon">{{ ind.icon }}</span>
          <span class="landing__ind-name">{{ ind.name }}</span>
        </div>
      </div>
    </section>

    <section class="landing__final-cta">
      <h2 class="landing__final-title">
        Stop losing sales. Start making better stock decisions today.
      </h2>
      <p class="landing__final-sub">
        Free for up to 5 products. Join hundreds of owners making smarter reorders.
      </p>
      <NuxtLink to="/auth/signup" class="btn btn-primary btn-lg">
        Start Free — See Your Risk Now
      </NuxtLink>
    </section>

    <footer class="landing__footer">
      <span class="landing__brand" style="font-size:14px">SiloXR</span>
      <span class="t-hint">©️ 2026 · The Business Decision Engine · Inventory Intelligence · <a :href="SITE_CONTACT_MAILTO" class="landing__footer-link">{{ SITE_CONTACT_EMAIL }}</a></span>
      <div style="display:flex;gap:16px">
        <NuxtLink to="/auth/login"  class="t-hint" style="text-decoration:none">Sign in</NuxtLink>
        <NuxtLink to="/auth/signup" class="t-hint" style="text-decoration:none">Create Free Account</NuxtLink>
      </div>
    </footer>

  </div>
</template>

<style scoped>
.landing {
  background: var(--bg);
  min-height: 100vh;
}

/* Nav */
.landing__nav {
  position:       sticky;
  top:            0;
  z-index:        100;
  background:     var(--bg-overlay);
  backdrop-filter: blur(16px);
  border-bottom:  1px solid var(--border-subtle);
  padding:        0 var(--page-pad);
}
.landing__nav-inner {
  max-width:       var(--page-max);
  margin:          0 auto;
  height:          56px;
  display:         flex;
  align-items:     center;
  justify-content: space-between;
}
.landing__brand {
  font-size:      16px;
  font-weight:    700;
  color:          var(--purple);
  letter-spacing: -0.03em;
  display:        flex;
  align-items:    center;
  gap:            8px;
}
.landing__brand-mark {
  width:         22px;
  height:        22px;
  border-radius: 6px;
  background:    linear-gradient(135deg, var(--purple), var(--purple-2));
  display:       flex;
  align-items:   center;
  justify-content: center;
}
.landing__nav-links {
  display:     flex;
  align-items: center;
  gap:         8px;
}
.landing__nav-link {
  font-size:     13px;
  font-weight:   500;
  color:         var(--text-3);
  padding:       6px 10px;
  border-radius: var(--r-sm);
  transition:    all var(--dur-fast);
}
.landing__nav-link:hover { color: var(--text); background: var(--border-subtle); }

/* Hero */
.landing__hero {
  max-width:   var(--page-max);
  margin:      0 auto;
  padding:     80px var(--page-pad) 60px;
  display:     grid;
  grid-template-columns: 1fr 380px;
  gap:         60px;
  align-items: center;
}
@media (max-width: 860px) {
  .landing__hero { grid-template-columns: 1fr; }
  .landing__hero-card { display: none; }
}
.landing__eyebrow {
  font-size:      11px;
  font-weight:    700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color:          var(--purple);
  background:     var(--purple-bg);
  display:        inline-block;
  padding:        4px 12px;
  border-radius:  99px;
  margin-bottom:  16px;
}
.landing__headline {
  font-size:      42px;
  font-weight:    800;
  letter-spacing: -0.04em;
  line-height:    1.12;
  color:          var(--text);
  margin-bottom:  16px;
}
@media (max-width: 640px) { .landing__headline { font-size: 30px; } }
.landing__headline-accent { color: var(--purple); }
.landing__sub {
  font-size:     17px;
  color:         var(--text-2);
  line-height:   1.65;
  max-width:     520px;
  margin-bottom: 28px;
}
.landing__hero-ctas { display: flex; gap: 12px; flex-wrap: wrap; }
.landing__hero-fine { font-size: 12px; color: var(--text-4); margin-top: 12px; }

/* Hero card mockup */
.landing__hero-card {
  border-radius: var(--r-xl);
  overflow:      hidden;
  display:       flex;
  box-shadow:    var(--shadow-xl);
  animation:     fade-up 0.6s var(--ease-out) 0.2s both;
}
.landing__mock-strip  { width: 4px; background: var(--sev-warning-strip); flex-shrink: 0; }
.landing__mock-body   { padding: 20px 22px; flex: 1; display: flex; flex-direction: column; gap: 10px; }
.landing__mock-sku    { font-size: 10px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--text-4); }
.landing__mock-action { font-size: 18px; font-weight: 700; color: var(--sev-warning-text); }
.landing__mock-reason { font-size: 13px; color: var(--text-2); line-height: 1.55; }
.landing__mock-conf   { display: flex; align-items: center; gap: 10px; }
.landing__mock-bar    { flex: 1; height: 5px; background: var(--border); border-radius: 99px; overflow: hidden; }
.landing__mock-fill   { height: 100%; background: var(--green); border-radius: 99px; }
.landing__mock-pct    { font-size: 12px; font-weight: 700; }

/* Features */
.landing__features {
  background: var(--bg-card);
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  padding: 72px var(--page-pad);
}
.landing__section-title {
  font-size:      26px;
  font-weight:    700;
  letter-spacing: -0.025em;
  color:          var(--text);
  text-align:     center;
  margin-bottom:  40px;
}
.landing__features-grid {
  max-width: var(--page-max);
  margin:    0 auto;
  display:   grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap:       16px;
}
.landing__feature-card {
  padding:        24px;
  display:        flex;
  flex-direction: column;
  gap:            10px;
  transition:     box-shadow var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out);
}
.landing__feature-card:hover { box-shadow: var(--shadow-hover); transform: translateY(-2px); }
.landing__feature-icon  { font-size: 24px; }
.landing__feature-title { font-size: 15px; font-weight: 600; color: var(--text); }
.landing__feature-desc  { font-size: 13px; color: var(--text-2); line-height: 1.6; }

/* How it works */
.landing__how       { padding: 72px var(--page-pad); }
.landing__how-inner { max-width: var(--page-max); margin: 0 auto; }
.landing__steps     { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 28px; }
.landing__step      { display: flex; gap: 16px; align-items: flex-start; }
.landing__step-num  {
  font-size:   11px;
  font-weight: 700;
  color:       var(--purple);
  background:  var(--purple-bg);
  padding:     4px 8px;
  border-radius: var(--r-sm);
  flex-shrink: 0;
  margin-top:  2px;
}
.landing__step-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.landing__step-desc  { font-size: 13px; color: var(--text-2); line-height: 1.55; }

/* Upload */
.landing__upload       { margin: 0 var(--page-pad) 0; max-width: var(--page-max); margin: 0 auto; padding: 40px; }
.landing__upload-inner { display: flex; justify-content: space-between; align-items: center; gap: 32px; flex-wrap: wrap; }
.landing__upload-title { font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
.landing__upload-desc  { font-size: 14px; color: var(--text-2); max-width: 420px; line-height: 1.6; }
.landing__upload-formats { display: flex; gap: 10px; }
.landing__format-badge {
  font-size:     12px;
  font-weight:   700;
  padding:       6px 16px;
  border-radius: var(--r-md);
  background:    var(--purple-bg);
  color:         var(--purple);
  letter-spacing: 0.04em;
}

/* Industries */
.landing__industries { padding: 72px var(--page-pad); max-width: var(--page-max); margin: 0 auto; }
.landing__ind-grid   { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.landing__ind-card   { padding: 18px 20px; display: flex; align-items: center; gap: 12px; transition: all var(--dur-base) var(--ease-out); }
.landing__ind-card:hover { box-shadow: var(--shadow-hover); transform: translateY(-2px); }
.landing__ind-icon   { font-size: 22px; }
.landing__ind-name   { font-size: 13px; font-weight: 600; color: var(--text); }

/* Final CTA */
.landing__final-cta {
  background:      linear-gradient(135deg, var(--purple-dark), var(--purple));
  padding:         80px var(--page-pad);
  text-align:      center;
  display:         flex;
  flex-direction:  column;
  align-items:     center;
  gap:             16px;
}
.landing__final-title { font-size: 30px; font-weight: 700; color: #fff; letter-spacing: -0.03em; }
.landing__final-sub   { font-size: 16px; color: rgba(255,255,255,0.7); }
.landing__final-cta .btn-primary {
  background:  #fff;
  color:       var(--purple);
  box-shadow:  0 4px 14px rgba(0,0,0,0.2);
}
.landing__final-cta .btn-primary:hover { background: rgba(255,255,255,0.92); }

/* Footer */
.landing__footer {
  padding:         24px var(--page-pad);
  border-top:      1px solid var(--border-subtle);
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  gap:             16px;
  flex-wrap:       wrap;
  max-width:       var(--page-max);
  margin:          0 auto;
}
.landing__footer-link {
  color: var(--purple);
  font-weight: 600;
  text-decoration: none;
}
.landing__footer-link:hover {
  text-decoration: underline;
}
</style>
