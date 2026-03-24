<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../constants/site"

const runtimeConfig = useRuntimeConfig()
const siteUrl = String(runtimeConfig.public.siteUrl || "https://siloxr.com").replace(/\/+$/, "")
const canonicalUrl = `${siteUrl}/`
const ogImageUrl = `${siteUrl}/og-image.svg`

const problemPoints = [
  {
    title: "Customers leave empty-handed",
    description:
      "You only realize you are out of a best-seller when a customer asks for it. That is revenue lost instantly.",
  },
  {
    title: "Your cash is tied up in the wrong products",
    description:
      "You overstock slow-moving items while fast-moving products run out.",
  },
  {
    title: "You rely on guesswork",
    description:
      "Manual counts and intuition lead to costly mistakes. One bad reorder can wipe out your margin.",
  },
]

const systemSteps = [
  "Collects your sales and inventory data",
  "Learns demand patterns over time",
  "Predicts stockout risks and revenue loss",
  "Recommends exactly what action to take",
]

const valuePoints = [
  {
    title: "Stop losing sales",
    description: "Know exactly when stock will run out days in advance.",
  },
  {
    title: "Protect your cash flow",
    description: "Avoid tying money down in slow-moving products.",
  },
  {
    title: "Turn messy data into clarity",
    description: "No perfect spreadsheets required. SiloXR works with what you already have.",
  },
  {
    title: "Operate without interruption",
    description: "Log sales and stock offline. Sync and analyze when you are back online.",
  },
  {
    title: "Get instant alerts",
    description: "Receive alert notifications when products enter risk zones.",
  },
  {
    title: "Improve every day",
    description: "The more you use SiloXR, the smarter and more accurate it becomes.",
  },
]

const differentiators = [
  {
    title: "Zero Data Perfection Required",
    description: "Most tools fail with messy data. SiloXR is built to find patterns in it.",
  },
  {
    title: "Built for real operations",
    description: "Fast, mobile, and offline-first, designed for the shop floor.",
  },
  {
    title: "Focused on profit, not reports",
    description: "No dashboards you ignore. Just clear daily actions that make or save money.",
  },
]

const startSteps = [
  {
    number: "1",
    title: "Connect your stock",
    description: "Upload your product list via CSV, Excel, or even a photo.",
  },
  {
    number: "2",
    title: "Log a few sales",
    description: "Record transactions in seconds, even without internet.",
  },
  {
    number: "3",
    title: "See your risk",
    description: "SiloXR identifies products trending toward stockouts.",
  },
  {
    number: "4",
    title: "Take action",
    description: "Get a daily Restock or Hold list to maximize profit.",
  },
]

const industries = [
  "Retail & FMCG",
  "Food & Beverage",
  "Pharmacies",
  "Wholesale & Distribution",
  "Mini-Supermarkets",
  "Hardware & Tools",
]

const faqs = [
  {
    question: "What does SiloXR do?",
    answer:
      "SiloXR predicts inventory risk, identifies potential stockouts, and recommends what to reorder to protect revenue.",
  },
  {
    question: "Who is SiloXR for?",
    answer:
      "Retailers, pharmacies, food businesses, wholesalers, and operators who need simple, accurate stock decisions without complex systems.",
  },
  {
    question: "Do I need perfect data?",
    answer:
      "No. SiloXR is designed to work with imperfect data and improve accuracy over time.",
  },
  {
    question: "Can I start for free?",
    answer:
      "Yes. You can use SiloXR for free with up to 5 products.",
  },
]

useSeoMeta({
  title: "SiloXR | The Inventory Decision Engine",
  description:
    "Stop losing revenue to stockouts before they happen. SiloXR analyzes sales patterns, detects stock risks, and tells you exactly what to reorder.",
  keywords:
    "inventory decision engine, stockout prevention software, reorder recommendations, inventory analytics, demand intelligence, inventory risk alerts",
  ogType: "website",
  ogUrl: canonicalUrl,
  ogTitle: "SiloXR | The Inventory Decision Engine",
  ogDescription:
    "SiloXR turns sales and inventory data into clear reorder actions, stockout risk signals, and profit-protecting decisions.",
  ogImage: ogImageUrl,
  twitterCard: "summary_large_image",
  twitterTitle: "SiloXR | Stop Losing Revenue to Stockouts",
  twitterDescription:
    "Analyze sales patterns, detect stock risks, and know exactly what to reorder before profit is lost.",
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
            "Inventory decision engine that detects stock risks and recommends what to reorder to protect revenue.",
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
          SiloXR analyzes your sales patterns, detects stock risks, and tells you exactly what to reorder to protect profit, even with messy data.
        </p>

        <div class="landing__hero-ctas">
          <NuxtLink to="/auth/signup" class="btn btn-primary btn-lg">Create Free Account</NuxtLink>
          <a href="#how-it-works" class="btn btn-secondary btn-lg">See How It Works</a>
        </div>

        <p class="landing__hero-fine">
          Free for up to 5 products. Setup takes 2 minutes. No credit card required.
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

    <section class="landing__section landing__section--problem">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">You are losing money every day if...</h2>
        <div class="landing__cards-grid">
          <article v-for="item in problemPoints" :key="item.title" class="landing__problem-card surface">
            <h3 class="landing__card-title">{{ item.title }}</h3>
            <p class="landing__card-copy">{{ item.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__section">
      <div class="landing__system surface">
        <div>
          <span class="landing__eyebrow">How SiloXR works</span>
          <h2 class="landing__section-title landing__section-title--left">Not just stock tracking, a decision engine</h2>
          <p class="landing__section-copy">
            SiloXR is not just stock tracking. It is a decision engine that turns raw operating data into clear action.
          </p>
          <p class="landing__section-copy">
            So instead of reacting late, you act early with clarity and confidence.
          </p>
        </div>
        <div class="landing__system-list">
          <div v-for="step in systemSteps" :key="step" class="landing__system-item">
            <span class="landing__system-dot" aria-hidden="true" />
            <span>{{ step }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="landing__section landing__section--soft">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">From data to decisions in seconds</h2>
        <div class="landing__cards-grid">
          <article v-for="item in valuePoints" :key="item.title" class="landing__value-card surface">
            <h3 class="landing__card-title">{{ item.title }}</h3>
            <p class="landing__card-copy">{{ item.description }}</p>
          </article>
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

    <section id="how-it-works" class="landing__section landing__section--soft">
      <div class="landing__section-inner">
        <h2 class="landing__section-title">Get your first reorder decision in under 10 minutes</h2>
        <div class="landing__steps">
          <article v-for="step in startSteps" :key="step.number" class="landing__step surface">
            <span class="landing__step-num">{{ step.number }}</span>
            <h3 class="landing__step-title">{{ step.title }}</h3>
            <p class="landing__step-desc">{{ step.description }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="landing__section">
      <div class="landing__upload surface">
        <div class="landing__upload-copy">
          <span class="landing__eyebrow">Already have a stock list?</span>
          <h2 class="landing__section-title landing__section-title--left">Stop manual entry. Upload your existing data and get instant insights.</h2>
          <p class="landing__section-copy">
            Bring in your current records and move straight to decision-ready inventory intelligence.
          </p>
          <div class="landing__upload-formats">
            <span class="landing__format-badge">CSV</span>
            <span class="landing__format-badge">Excel</span>
            <span class="landing__format-badge">PDF</span>
          </div>
        </div>
        <div class="landing__upload-actions">
          <NuxtLink to="/auth/signup" class="btn btn-primary">Create Free Account</NuxtLink>
          <NuxtLink to="/upload" class="btn btn-secondary">Open Upload Flow</NuxtLink>
        </div>
      </div>
    </section>

    <section class="landing__section landing__section--statement">
      <div class="landing__section-inner">
        <div class="landing__statement">
          <span class="landing__eyebrow">Built as a decision intelligence layer</span>
          <p class="landing__statement-copy">
            SiloXR sits on top of your existing operations and turns raw data into clear, profit-driven actions.
          </p>
          <p class="landing__statement-note">
            No ERP required. No perfect data needed. Just better decisions, every day.
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
          Join operators using SiloXR to protect revenue and optimize inventory daily.
        </p>
        <p class="landing__final-note">
          Free for up to 5 products. No credit card required.
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
        <span>© 2026 SiloXR. All rights reserved.</span>
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

.landing__upload {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 30px 32px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--purple) 10%, transparent), transparent 32%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 92%, transparent));
}

.landing__upload-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 220px;
}

.landing__upload-formats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.landing__format-badge {
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--purple) 12%, transparent);
  color: var(--purple);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
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
  .landing__upload {
    grid-template-columns: 1fr;
  }

  .landing__upload {
    flex-direction: column;
    align-items: flex-start;
  }

  .landing__upload-actions {
    min-width: 0;
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }

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
  .landing__industry-grid {
    grid-template-columns: 1fr;
  }

  .landing__hero-card,
  .landing__system,
  .landing__upload,
  .landing__problem-card,
  .landing__value-card,
  .landing__diff-card,
  .landing__faq-card,
  .landing__step {
    padding: 22px;
  }
}
</style>
