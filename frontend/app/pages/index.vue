<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../constants/site"

const runtimeConfig = useRuntimeConfig()
const siteUrl = String(runtimeConfig.public.siteUrl || "https://siloxr.com").replace(/\/+$/, "")
const canonicalUrl = `${siteUrl}/`
const ogImageUrl = `${siteUrl}/og-image.svg`

const problemPoints = [
  {
    title: "Stockouts = lost revenue",
    description:
      "Customers leave when products are unavailable and rarely return.",
  },
  {
    title: "Overstock = trapped cash",
    description:
      "Money sits in slow-moving products instead of fueling growth.",
  },
  {
    title: "Guesswork = inconsistent decisions",
    description:
      "Manual tracking leads to costly errors and missed opportunities.",
  },
]

const valuePoints = [
  {
    title: "Prevent stockouts",
    description: "Know exactly when products will run out before it happens.",
  },
  {
    title: "Improve cash flow",
    description: "Stop overbuying slow-moving inventory.",
  },
  {
    title: "Make faster decisions",
    description: "Get clear daily actions instead of analyzing spreadsheets.",
  },
  {
    title: "Operate without interruption",
    description: "Log and track inventory even without internet.",
  },
  {
    title: "Stay informed in real-time",
    description: "Receive alerts when products enter risk zones.",
  },
]

const differentiators = [
  {
    title: "Works with messy data",
    description: "No perfect systems required.",
  },
  {
    title: "Built for real operations",
    description: "Fast, mobile, offline-first.",
  },
  {
    title: "Focused on decisions, not dashboards",
    description: "No complex reports, just clear actions.",
  },
]

const startSteps = [
  {
    number: "1",
    title: "Upload your stock",
    description: "CSV, Excel, or photo.",
  },
  {
    number: "2",
    title: "Record a few sales",
    description: "Quick and simple.",
  },
  {
    number: "3",
    title: "See your risk",
    description: "Identify products trending toward stockout.",
  },
  {
    number: "4",
    title: "Take action",
    description: "Follow daily Restock or Hold recommendations.",
  },
]

const operatingSteps = [
  {
    number: "1",
    title: "Capture data",
    description: "Sales and stock are recorded, even offline.",
  },
  {
    number: "2",
    title: "Analyze demand patterns",
    description: "SiloXR identifies trends and changes in product movement.",
  },
  {
    number: "3",
    title: "Predict risk",
    description: "Detects when products are likely to run out.",
  },
  {
    number: "4",
    title: "Recommend actions",
    description: "Clear Restock or Hold decisions based on real data.",
  },
]

const proofSignals = [
  "N12,400 revenue at risk this week",
  "Stockout expected in about 2 days",
  "Demand trending +15% above normal",
]

const financialImpactPoints = [
  "Reduce stockouts and missed sales",
  "Improve availability of high-demand products",
  "Free up cash tied in slow-moving inventory",
  "Make consistent, data-backed decisions",
]

const industries = [
  "Retail & FMCG",
  "Food & Beverage",
  "Pharmacies",
  "Wholesale & Distribution",
  "Supermarkets",
  "Hardware & Tools",
]

const faqs = [
  {
    question: "What does SiloXR do?",
    answer:
      "SiloXR helps businesses track inventory risk, identify likely stockouts, and decide what to reorder before sales are lost.",
  },
  {
    question: "Who is SiloXR built for?",
    answer:
      "SiloXR is designed for retail shops, pharmacies, food businesses, wholesalers, supermarkets, and other operators who need simple stock decisions without heavy ERP software.",
  },
  {
    question: "Do I need perfect data?",
    answer:
      "No. SiloXR is built to work with imperfect sales and stock logs, then improve decision quality as more data is recorded over time.",
  },
  {
    question: "Can I start for free?",
    answer:
      "Yes. SiloXR offers a free tier for businesses getting started with a limited number of products.",
  },
]

useSeoMeta({
  title: "SiloXR | The Inventory Decision Engine",
  description:
    "Stop losing revenue to stockouts before they happen. SiloXR analyzes sales patterns and demand trends to predict stock risks and tell you what to reorder.",
  keywords:
    "inventory decision engine, stockout prevention software, reorder recommendations, demand trends, inventory risk alerts, demand forecasting inventory, reorder decision software",
  ogType: "website",
  ogUrl: canonicalUrl,
  ogTitle: "SiloXR | The Inventory Decision Engine",
  ogDescription:
    "Stop losing revenue to stockouts before they happen. SiloXR analyzes sales patterns and demand trends to predict stock risks and tell you what to reorder.",
  ogImage: ogImageUrl,
  twitterCard: "summary_large_image",
  twitterTitle: "SiloXR | The Inventory Decision Engine",
  twitterDescription:
    "Analyze sales patterns and demand trends to predict stock risks and know exactly what to reorder before profit is lost.",
  twitterImage: ogImageUrl,
})

useHead({
  link: [
    { rel: "canonical", href: canonicalUrl },
  ],
  script: [
    {
      key: "ld-json-home",
      type: "application/ld+json",
      children: JSON.stringify([
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          name: "SiloXR",
          url: canonicalUrl,
          email: SITE_CONTACT_EMAIL,
          logo: ogImageUrl,
        },
        {
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          name: "SiloXR",
          applicationCategory: "BusinessApplication",
          operatingSystem: "Web",
          offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "USD",
          },
          description:
            "Inventory decision engine that analyzes sales patterns and demand trends to predict stock risks and recommend what to reorder.",
          url: canonicalUrl,
        },
        {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: faqs.map((item) => ({
            "@type": "Question",
            name: item.question,
            acceptedAnswer: {
              "@type": "Answer",
              text: item.answer,
            },
          })),
        },
      ]),
    },
  ],
})
</script>

<template>
  <div class="landing">
    <nav class="landing__nav">
      <div class="landing__nav-inner">
        <div class="landing__brand">
          <div class="landing__brand-mark" aria-hidden="true">
            <img src="/logo-mark.svg" alt="" />
          </div>
          <div>
            <strong>SiloXR</strong>
            <span class="landing__brand-line">The Inventory Decision Engine</span>
          </div>
        </div>

        <div class="landing__nav-links">
          <a href="#how-it-works" class="landing__nav-link">How it works</a>
          <a href="#industries" class="landing__nav-link">Industries</a>
          <a href="#faq" class="landing__nav-link">FAQ</a>
          <NuxtLink to="/auth/login" class="landing__nav-link">Sign in</NuxtLink>
          <NuxtLink to="/auth/signup" class="btn btn-primary btn-sm">Create Free Account</NuxtLink>
        </div>
      </div>
    </nav>

    <section class="landing__hero">
      <div class="landing__hero-copy">
        <span class="landing__eyebrow">Decision intelligence for inventory operations</span>
        <h1 class="landing__headline">
          SiloXR, the inventory decision engine
        </h1>
        <p class="landing__headline-sub">
          Stop losing revenue to stockouts before they happen.
        </p>
        <p class="landing__sub">
          SiloXR analyzes your sales patterns and demand trends to predict stock risks and tells you exactly what to reorder to protect your profit.
        </p>

        <div class="landing__hero-ctas">
          <NuxtLink to="/auth/signup" class="btn btn-primary btn-lg">Create Free Account</NuxtLink>
          <a href="#how-it-works" class="btn btn-secondary btn-lg">See How It Works</a>
        </div>

        <p class="landing__hero-fine">
          Free for up to 5 products · Setup in 2 minutes · No credit card required
        </p>
      </div>

      <div class="landing__hero-card surface-raised">
        <div class="landing__live-label">Live example</div>
        <div class="landing__mock-strip" />
        <div class="landing__mock-body">
          <div class="landing__mock-sku">SKU: PALM-OIL-5L</div>
          <div class="landing__mock-action">RESTOCK IMMEDIATELY</div>
          <div class="landing__mock-reason">
            <strong>N12,400 at risk this week</strong>
          </div>
          <p class="landing__mock-copy">
            Based on demand trends, you will run out in about 2 days. Demand is trending 15% above normal.
          </p>
          <div class="landing__mock-conf">
            <div class="landing__mock-bar">
              <div class="landing__mock-fill" style="width: 94%" />
            </div>
            <span class="landing__mock-pct">Risk Level: 94%</span>
          </div>
        </div>
      </div>
    </section>

    <section class="landing__section landing__section--proof">
      <div class="landing__section-inner">
        <div class="landing__proof surface">
          <div>
            <span class="landing__eyebrow">Decisions you can act on immediately</span>
          </div>
          <div class="landing__proof-list">
            <div v-for="item in proofSignals" :key="item" class="landing__proof-item">{{ item }}</div>
          </div>
          <div class="landing__proof-action">Recommended action: Restock now</div>
        </div>
      </div>
    </section>

    <section class="landing__section landing__section--problem">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">Inventory mistakes quietly kill profit</h2>
        <div class="landing__cards-grid">
          <article v-for="item in problemPoints" :key="item.title" class="landing__problem-card surface">
            <h3 class="landing__card-title">{{ item.title }}</h3>
            <p class="landing__card-copy">{{ item.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__section">
      <div class="landing__shift surface">
        <span class="landing__eyebrow">From tracking inventory to making decisions</span>
        <h2 class="landing__section-title landing__section-title--left">Most tools show you what happened.</h2>
        <p class="landing__shift-accent">SiloXR tells you what to do next.</p>
      </div>
    </section>

    <section id="how-it-works" class="landing__section landing__section--soft">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">A simple system that turns data into decisions</h2>
        <div class="landing__steps">
          <article v-for="step in operatingSteps" :key="step.number" class="landing__step surface">
            <span class="landing__step-num">{{ step.number }}</span>
            <h3 class="landing__step-title">{{ step.title }}</h3>
            <p class="landing__step-desc">{{ step.description }}</p>
          </article>
        </div>
        <p class="landing__section-note">No perfect data required. Accuracy improves as you use it.</p>
      </div>
    </section>

    <section class="landing__section">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">From data to profit-driven decisions</h2>
        <div class="landing__cards-grid">
          <article v-for="item in valuePoints" :key="item.title" class="landing__value-card surface">
            <h3 class="landing__card-title">{{ item.title }}</h3>
            <p class="landing__card-copy">{{ item.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__section landing__section--soft">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">What this means for your business</h2>
        <div class="landing__impact surface">
          <div class="landing__impact-list">
            <div v-for="item in financialImpactPoints" :key="item" class="landing__impact-item">
              {{ item }}
            </div>
          </div>
          <div class="landing__impact-copy">
            <p>Every stockout is lost revenue.</p>
            <p>Every overstock is idle capital.</p>
            <p><strong>SiloXR helps you minimize both.</strong></p>
          </div>
        </div>
      </div>
    </section>

    <section class="landing__section">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">Why smart operators choose SiloXR</h2>
        <div class="landing__cards-grid landing__cards-grid--three">
          <article v-for="item in differentiators" :key="item.title" class="landing__diff-card surface">
            <h3 class="landing__card-title">{{ item.title }}</h3>
            <p class="landing__card-copy">{{ item.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__section">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">Get your first decision in under 10 minutes</h2>
        <div class="landing__steps">
          <article v-for="step in startSteps" :key="step.number" class="landing__step surface">
            <span class="landing__step-num">{{ step.number }}</span>
            <h3 class="landing__step-title">{{ step.title }}</h3>
            <p class="landing__step-desc">{{ step.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__section landing__section--statement">
      <div class="landing__section-inner">
        <div class="landing__statement">
          <span class="landing__eyebrow">Built to grow with your business</span>
          <p class="landing__statement-copy">
            Whether you manage a single shop or multiple locations, SiloXR adapts and improves as your operations expand.
          </p>
        </div>
      </div>
    </section>

    <section id="industries" class="landing__section">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">Built for businesses that cannot afford stock mistakes</h2>
        <div class="landing__industry-grid">
          <div v-for="industry in industries" :key="industry" class="landing__industry surface">
            {{ industry }}
          </div>
        </div>
      </div>
    </section>

    <section id="faq" class="landing__section landing__section--soft">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">Frequently asked questions</h2>
        <div class="landing__cards-grid">
          <article v-for="item in faqs" :key="item.question" class="landing__faq-card surface">
            <h3 class="landing__card-title">{{ item.question }}</h3>
            <p class="landing__card-copy">{{ item.answer }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__final">
      <div class="landing__final-inner">
        <h2 class="landing__final-title">Stop losing sales. Start making smarter decisions.</h2>
        <p class="landing__final-copy">
          Join operators using SiloXR to protect revenue and improve inventory decisions every day.
        </p>
        <NuxtLink to="/auth/signup" class="btn btn-primary btn-lg landing__final-btn">
          Create Free Account
        </NuxtLink>
      </div>
    </section>

    <footer class="landing__footer">
      <div>
        <div class="landing__footer-brand">SiloXR</div>
        <div class="landing__footer-line">The Inventory Decision Engine</div>
      </div>
      <div class="landing__footer-meta">
        <span>© 2026 SiloXR</span>
        <a :href="SITE_CONTACT_MAILTO" class="landing__footer-link">{{ SITE_CONTACT_EMAIL }}</a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--purple) 10%, transparent), transparent 32%),
    linear-gradient(180deg, var(--bg), color-mix(in srgb, var(--bg) 92%, white 8%));
}

.landing__nav {
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-overlay) 92%, white 8%);
  backdrop-filter: blur(16px);
  padding: 0 var(--page-pad);
}

.landing__nav-inner {
  max-width: var(--page-max);
  height: 64px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.landing__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
}

.landing__brand strong,
.landing__footer-brand {
  display: block;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--purple);
}

.landing__brand-line,
.landing__footer-line {
  display: block;
  font-size: 11px;
  color: var(--text-4);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.landing__brand-mark {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.landing__brand-mark img {
  width: 100%;
  height: 100%;
  display: block;
}

.landing__nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.landing__nav-link {
  padding: 7px 10px;
  border-radius: var(--r-sm);
  color: var(--text-3);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: all var(--dur-fast);
}

.landing__nav-link:hover {
  color: var(--text);
  background: color-mix(in srgb, var(--purple) 8%, transparent);
}

.landing__hero,
.landing__section-inner,
.landing__footer {
  max-width: var(--page-max);
  margin: 0 auto;
}

.landing__hero {
  padding: 88px var(--page-pad) 72px;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
  gap: 48px;
  align-items: center;
}

.landing__hero-copy {
  max-width: 640px;
}

.landing__eyebrow {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--purple) 12%, transparent);
  color: var(--purple);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.landing__headline {
  margin: 18px 0 0;
  font-size: clamp(40px, 6vw, 64px);
  line-height: 0.98;
  letter-spacing: -0.05em;
  color: var(--text);
}

.landing__headline-sub {
  margin: 16px 0 0;
  font-size: clamp(22px, 3vw, 30px);
  line-height: 1.15;
  letter-spacing: -0.03em;
  color: var(--purple-dark);
}

.landing__sub,
.landing__section-copy,
.landing__card-copy,
.landing__step-desc,
.landing__final-copy {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-2);
}

.landing__sub {
  margin: 18px 0 0;
  max-width: 56ch;
}

.landing__hero-ctas {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 28px;
}

.landing__hero-fine,
.landing__final-note {
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-4);
}

.landing__hero-card {
  position: relative;
  overflow: hidden;
  padding: 22px;
  border-radius: 28px;
  border: 1px solid color-mix(in srgb, var(--danger, #d14a5f) 18%, var(--border-subtle));
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--danger, #d14a5f) 12%, transparent), transparent 34%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 90%, transparent));
  box-shadow: var(--shadow-xl);
}

.landing__live-label {
  margin-bottom: 18px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-4);
}

.landing__mock-strip {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  background: var(--danger, #d14a5f);
}

.landing__mock-body {
  display: grid;
  gap: 12px;
}

.landing__mock-sku {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-4);
}

.landing__mock-action {
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--danger, #d14a5f);
  font-weight: 800;
}

.landing__mock-reason {
  font-size: 22px;
  line-height: 1.15;
  letter-spacing: -0.03em;
  color: var(--text);
}

.landing__mock-copy {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-2);
}

.landing__mock-conf {
  display: grid;
  gap: 10px;
  margin-top: 6px;
}

.landing__mock-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--border) 84%, transparent);
}

.landing__mock-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--danger, #d14a5f) 72%, #ff9b8f), var(--danger, #d14a5f));
}

.landing__mock-pct {
  font-size: 13px;
  font-weight: 700;
  color: var(--danger, #d14a5f);
}

.landing__section {
  padding: 0 var(--page-pad) 80px;
}

.landing__section--proof {
  padding-top: 0;
}

.landing__section--soft {
  background: color-mix(in srgb, var(--bg-card) 80%, transparent);
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  padding-top: 80px;
}

.landing__section--problem {
  padding-top: 16px;
}

.landing__section--statement {
  padding-top: 12px;
}

.landing__section-title {
  margin: 0;
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.05;
  letter-spacing: -0.04em;
  color: var(--text);
  text-align: center;
}

.landing__section-title--left {
  text-align: left;
}

.landing__section-inner > .landing__section-title + .landing__cards-grid,
.landing__section-inner > .landing__section-title + .landing__steps,
.landing__section-inner > .landing__section-title + .landing__industry-grid {
  margin-top: 36px;
}

.landing__section-copy {
  margin: 14px 0 0;
  max-width: 56ch;
}

.landing__cards-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 36px;
}

.landing__cards-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.landing__proof,
.landing__shift,
.landing__impact {
  padding: 28px 30px;
  border-radius: 26px;
}

.landing__proof {
  display: grid;
  gap: 18px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--purple) 12%, transparent), transparent 34%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 92%, transparent));
}

.landing__proof-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.landing__proof-item,
.landing__impact-item {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--purple) 14%, var(--border-subtle));
  background: color-mix(in srgb, var(--purple) 5%, var(--bg-card));
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-2);
}

.landing__proof-action {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--purple-dark);
}

.landing__problem-card,
.landing__value-card,
.landing__diff-card,
.landing__faq-card {
  padding: 24px;
  border-radius: 22px;
}

.landing__problem-card {
  border-top: 3px solid color-mix(in srgb, var(--danger, #d14a5f) 82%, white 18%);
}

.landing__card-title {
  margin: 0;
  font-size: 19px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--text);
}

.landing__card-copy {
  margin: 10px 0 0;
}

.landing__system {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
  gap: 28px;
  padding: 32px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--purple) 12%, transparent), transparent 36%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 92%, transparent));
}

.landing__shift {
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--purple) 12%, transparent), transparent 32%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 92%, transparent));
}

.landing__shift-accent {
  margin: 12px 0 0;
  font-size: clamp(24px, 4vw, 34px);
  line-height: 1.15;
  letter-spacing: -0.04em;
  color: var(--purple-dark);
  font-weight: 800;
}

.landing__system-list {
  display: grid;
  gap: 12px;
  align-content: start;
}

.landing__system-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--purple) 16%, var(--border-subtle));
  background: color-mix(in srgb, var(--purple) 6%, var(--bg-card));
  color: var(--text-2);
  line-height: 1.6;
}

.landing__system-dot {
  width: 10px;
  height: 10px;
  margin-top: 7px;
  border-radius: 999px;
  background: var(--purple);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--purple) 14%, transparent);
}

.landing__steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.landing__section-note {
  margin: 20px auto 0;
  max-width: 56ch;
  text-align: center;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-3);
}

.landing__step {
  padding: 22px;
  border-radius: 22px;
}

.landing__step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 34px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--purple) 12%, transparent);
  color: var(--purple);
  font-size: 14px;
  font-weight: 800;
}

.landing__step-title {
  margin: 16px 0 0;
  font-size: 17px;
  line-height: 1.2;
  color: var(--text);
}

.landing__step-desc {
  margin: 10px 0 0;
}

.landing__impact {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(260px, .85fr);
  gap: 18px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--purple) 12%, transparent), transparent 38%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 92%, transparent));
}

.landing__impact-list {
  display: grid;
  gap: 12px;
}

.landing__impact-copy {
  padding: 18px 20px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--purple) 6%, var(--bg-card));
  border: 1px solid color-mix(in srgb, var(--purple) 14%, var(--border-subtle));
  color: var(--text-2);
  line-height: 1.7;
}

.landing__impact-copy p {
  margin: 0;
}

.landing__impact-copy p + p {
  margin-top: 8px;
}

.landing__statement {
  max-width: 760px;
  margin: 0 auto;
  text-align: center;
}

.landing__statement-copy {
  margin: 18px 0 0;
  font-size: clamp(24px, 4vw, 34px);
  line-height: 1.18;
  letter-spacing: -0.04em;
  color: var(--text);
}

.landing__statement-note {
  margin: 14px 0 0;
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-2);
}

.landing__industry-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.landing__industry {
  padding: 20px 22px;
  border-radius: 20px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text);
  text-align: center;
}

.landing__final {
  padding: 88px var(--page-pad);
  background: linear-gradient(135deg, var(--purple-dark), var(--purple));
}

.landing__final-inner {
  max-width: 720px;
  margin: 0 auto;
  text-align: center;
}

.landing__final-title {
  margin: 0;
  font-size: clamp(34px, 5vw, 52px);
  line-height: 1.02;
  letter-spacing: -0.05em;
  color: #fff;
}

.landing__final-copy {
  margin: 16px auto 0;
  max-width: 52ch;
  color: rgba(255, 255, 255, 0.82);
}

.landing__final-btn {
  margin-top: 22px;
  background: #fff;
  color: var(--purple);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.18);
}

.landing__footer {
  padding: 28px var(--page-pad) 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.landing__footer-meta {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  color: var(--text-4);
  font-size: 13px;
}

.landing__footer-link {
  color: var(--purple);
  font-weight: 700;
  text-decoration: none;
}

.landing__footer-link:hover {
  text-decoration: underline;
}

@media (max-width: 1040px) {
  .landing__hero,
  .landing__system,
  .landing__impact {
    grid-template-columns: 1fr;
  }

  .landing__proof-list,
  .landing__cards-grid,
  .landing__steps,
  .landing__industry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .landing__nav-inner {
    height: auto;
    padding: 14px 0;
    align-items: flex-start;
    flex-direction: column;
  }

  .landing__hero {
    padding-top: 56px;
  }

  .landing__cards-grid,
  .landing__steps,
  .landing__industry-grid,
  .landing__proof-list {
    grid-template-columns: 1fr;
  }

  .landing__hero-card,
  .landing__system,
  .landing__proof,
  .landing__shift,
  .landing__impact,
  .landing__problem-card,
  .landing__value-card,
  .landing__diff-card,
  .landing__faq-card,
  .landing__step {
    padding: 22px;
  }
}
</style>
