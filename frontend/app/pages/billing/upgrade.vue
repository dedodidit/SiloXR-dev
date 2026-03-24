<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../../constants/site"

const { $api } = useNuxtApp()
const route = useRoute()

type BillingPlan = {
  key: string
  label: string
  interval: string
  currency: string
  amount: number | null
  amount_usd_reference: number | null
  pricing_tier: string
  contact_sales: boolean
}

type NotificationStatus = {
  preferred_channel: string
  recommended_channel: string
  issues: string[]
  email: {
    enabled: boolean
    configured: boolean
    ready: boolean
    address: string
    last_sent_at: string | null
  }
  telegram: {
    enabled: boolean
    linked: boolean
    ready: boolean
    username: string
    last_sent_at: string | null
  }
  whatsapp: {
    ready: boolean
    enabled: boolean
    issue: string
  }
}

const profile = ref<any>(null)
const plans = ref<BillingPlan[]>([])
const notificationStatus = ref<NotificationStatus | null>(null)
const pricingCountry = ref("")
const pricingCurrency = ref("USD")
const startingCheckout = ref("")
const verifying = ref(false)
const paymentMessage = ref("")
const paymentError = ref("")

const planOutcomes: Record<string, { tag: string; summary: string; bullets: string[] }> = {
  free: {
    tag: "Start here",
    summary: "Track products, stock, and sales while SiloXR begins reading your business.",
    bullets: [
      "Create products and record sales or stock",
      "Basic operating signals without money values",
      "Best for setting up your data layer",
    ],
  },
  core: {
    tag: "Decision layer",
    summary: "See quantified demand gaps and get clear next actions without the forecasting layer.",
    bullets: [
      "Revenue gap values and product-level gaps",
      "Prioritized actions and decision queue",
      "Best for teams ready to act on quantified signals",
    ],
  },
  pro: {
    tag: "Intelligence layer",
    summary: "Unlock forecasting, confidence bands, portfolio insights, and Business Health.",
    bullets: [
      "Forecasts, trends, and confidence bands",
      "Business Health and portfolio-level views",
      "Best for operators running SiloXR continuously",
    ],
  },
  enterprise: {
    tag: "Custom rollout",
    summary: "Multi-location, integrations, API access, and a tailored rollout.",
    bullets: [
      "Integrations and API access",
      "Multi-location support",
      "Contact-sales onboarding",
    ],
  },
}

const comparisonRows = [
  { label: "Track products, stock, and sales", free: true, core: true, pro: true },
  { label: "Quantified revenue gaps", free: false, core: true, pro: true },
  { label: "Prioritized actions", free: false, core: true, pro: true },
  { label: "Forecasting and confidence bands", free: false, core: false, pro: true },
  { label: "Business Health and portfolio insights", free: false, core: false, pro: true },
]

const currentPlan = computed(() => String(profile.value?.tier || "free").toLowerCase())
const primaryPlans = computed(() => sortedPlans.value.filter((plan) => !plan.contact_sales))
const enterprisePlan = computed(() => sortedPlans.value.find((plan) => plan.contact_sales) ?? null)
const nextRecommendedPlan = computed(() => {
  if (currentPlan.value === "free") return "core"
  if (currentPlan.value === "core") return "pro"
  if (currentPlan.value === "pro") return "enterprise"
  return "enterprise"
})

const currentPlanLabel = computed(() => currentPlan.value.toUpperCase())
const nextPlanLabel = computed(() => nextRecommendedPlan.value.toUpperCase())
const currentPlanOutcome = computed(() => planOutcomes[currentPlan.value] ?? planOutcomes.free)
const nextPlanOutcome = computed(() => planOutcomes[nextRecommendedPlan.value] ?? planOutcomes.pro)

const formatPrice = (plan: BillingPlan) => {
  if (plan.amount == null) return "Contact sales"
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: plan.currency || pricingCurrency.value || "USD",
    maximumFractionDigits: 0,
  }).format(plan.amount)
}

const sortedPlans = computed(() => {
  const order = ["free", "core", "pro", "enterprise"]
  return [...plans.value].sort((a, b) => order.indexOf(a.label.toLowerCase()) - order.indexOf(b.label.toLowerCase()))
})

const channelSummary = computed(() => {
  const status = notificationStatus.value
  if (!status) return "Checking notification readiness..."
  if (status.preferred_channel === "telegram" && status.telegram.ready) {
    return "Telegram is ready for live delivery."
  }
  if (status.email.ready) {
    return `Email is ready at ${status.email.address}.`
  }
  return "Only in-app notifications are guaranteed right now."
})

const channelTone = computed(() => {
  const status = notificationStatus.value
  if (!status) return "warning"
  return status.issues.length ? "warning" : "safe"
})

const loadProfile = async () => {
  try {
    profile.value = await $api("/profile/")
  } catch {}
}

const loadPlans = async () => {
  try {
    const data = await $api<{ country?: string; currency?: string; plans?: BillingPlan[] }>("/billing/plans/")
    plans.value = Array.isArray(data?.plans) ? data.plans : []
    pricingCountry.value = String(data?.country || "")
    pricingCurrency.value = String(data?.currency || "USD")
  } catch {}
}

const loadNotificationStatus = async () => {
  try {
    notificationStatus.value = await $api<NotificationStatus>("/notifications/status/")
  } catch {}
}

const startCheckout = async (planKey: string) => {
  startingCheckout.value = planKey
  paymentError.value = ""
  paymentMessage.value = ""

  try {
    const data = await $api<{ authorization_url: string }>("/billing/paystack/initialize/", {
      method: "POST",
      body: { plan: planKey },
    })

    if (process.client && data?.authorization_url) {
      window.location.href = data.authorization_url
    }
  } catch (e: any) {
    paymentError.value = e?.data?.detail ?? "We could not start checkout."
  } finally {
    startingCheckout.value = ""
  }
}

const verifyPayment = async (reference: string) => {
  verifying.value = true
  paymentError.value = ""

  try {
    const data = await $api<{ verified: boolean; message: string }>(
      `/billing/paystack/verify/?reference=${encodeURIComponent(reference)}`
    )
    paymentMessage.value = data.message
    await Promise.all([loadProfile(), loadPlans(), loadNotificationStatus()])
  } catch (e: any) {
    paymentError.value = e?.data?.detail ?? "We could not confirm the payment yet."
  } finally {
    verifying.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadProfile(), loadPlans(), loadNotificationStatus()])

  const reference = String(route.query.reference || route.query.trxref || "").trim()
  if (reference) {
    await verifyPayment(reference)
  }
})

useHead({ title: "SiloXR - Billing" })
</script>

<template>
  <div class="bill page-pad">
    <section class="bill__hero surface">
      <div class="bill__hero-main">
        <p class="bill__eyebrow">Billing</p>
        <h1 class="bill__title">Pick the plan that matches the decisions you need next.</h1>
        <p class="bill__sub">
          You are currently on <strong>{{ currentPlanLabel }}</strong>. The next logical step is
          <strong>{{ nextPlanLabel }}</strong> if you want {{ nextPlanOutcome.summary.toLowerCase() }}.
        </p>
        <div class="bill__hero-meta">
          <span>Market: <strong>{{ pricingCountry || "Default tier" }}</strong></span>
          <span>Currency: <strong>{{ pricingCurrency }}</strong></span>
        </div>
      </div>

      <div class="bill__hero-side">
        <p class="bill__mini-label">Current plan</p>
        <strong class="bill__mini-value">{{ currentPlanLabel }}</strong>
        <p class="bill__mini-copy">{{ currentPlanOutcome.summary }}</p>
        <a :href="SITE_CONTACT_MAILTO" class="bill__contact-link">{{ SITE_CONTACT_EMAIL }}</a>
      </div>
    </section>

    <section class="bill__readiness surface" :class="`bill__readiness--${channelTone}`">
      <div>
        <p class="bill__section-eyebrow">Notifications</p>
        <h2 class="bill__section-title">Notification readiness</h2>
        <p class="bill__section-copy">{{ channelSummary }}</p>
      </div>
      <div class="bill__readiness-grid">
        <div class="bill__channel">
          <span class="bill__channel-label">Email</span>
          <strong>{{ notificationStatus?.email.ready ? "Ready" : "Needs attention" }}</strong>
          <span class="bill__channel-meta">{{ notificationStatus?.email.address || "No email address" }}</span>
        </div>
        <div class="bill__channel">
          <span class="bill__channel-label">Telegram</span>
          <strong>{{ notificationStatus?.telegram.ready ? "Ready" : "Not linked" }}</strong>
          <span class="bill__channel-meta">
            {{ notificationStatus?.telegram.username ? `@${notificationStatus.telegram.username}` : "Link from profile" }}
          </span>
        </div>
      </div>
      <ul v-if="notificationStatus?.issues?.length" class="bill__issues">
        <li v-for="issue in notificationStatus.issues" :key="issue">{{ issue }}</li>
      </ul>
    </section>

    <section class="bill__plans">
      <article
        v-for="plan in primaryPlans"
        :key="plan.key"
        class="bill__card surface"
        :class="{
          'bill__card--featured': plan.label.toLowerCase() === nextRecommendedPlan,
          'bill__card--active': currentPlan === plan.label.toLowerCase(),
        }"
      >
        <div class="bill__card-top">
          <div>
            <p class="bill__plan">{{ plan.label }}</p>
            <p class="bill__tag">{{ planOutcomes[plan.label.toLowerCase()]?.tag }}</p>
          </div>
          <span v-if="currentPlan === plan.label.toLowerCase()" class="bill__badge">Current</span>
          <span v-else-if="plan.label.toLowerCase() === nextRecommendedPlan" class="bill__badge bill__badge--recommended">Recommended</span>
        </div>

        <h2 class="bill__price">
          {{ formatPrice(plan) }}
          <span v-if="plan.amount != null" class="bill__interval">/ {{ plan.interval }}</span>
        </h2>

        <p class="bill__desc">{{ planOutcomes[plan.label.toLowerCase()]?.summary }}</p>

        <ul class="bill__list">
          <li v-for="item in planOutcomes[plan.label.toLowerCase()]?.bullets || []" :key="item">{{ item }}</li>
        </ul>

        <button
          v-if="plan.label.toLowerCase() === 'core' || plan.label.toLowerCase() === 'pro'"
          class="bill__cta"
          :class="{ 'bill__cta--featured': plan.label.toLowerCase() === nextRecommendedPlan }"
          :disabled="startingCheckout === plan.key || verifying || currentPlan === plan.label.toLowerCase()"
          @click="startCheckout(plan.key)"
        >
          {{
            currentPlan === plan.label.toLowerCase()
              ? "Current plan"
              : startingCheckout === plan.key
                ? "Starting checkout..."
                : `Choose ${plan.label}`
          }}
        </button>

        <span v-else class="bill__cta bill__cta--muted">Included</span>
      </article>
    </section>

    <section class="bill__compare surface">
      <p class="bill__section-eyebrow">Compare quickly</p>
      <h2 class="bill__section-title">What actually changes by plan</h2>
      <div class="bill__table">
        <div class="bill__table-head">Capability</div>
        <div class="bill__table-head">Free</div>
        <div class="bill__table-head">Core</div>
        <div class="bill__table-head">Pro</div>

        <template v-for="row in comparisonRows" :key="row.label">
          <div class="bill__table-label">{{ row.label }}</div>
          <div class="bill__table-cell">{{ row.free ? "Yes" : "No" }}</div>
          <div class="bill__table-cell">{{ row.core ? "Yes" : "No" }}</div>
          <div class="bill__table-cell">{{ row.pro ? "Yes" : "No" }}</div>
        </template>
      </div>
    </section>

    <section v-if="enterprisePlan" class="bill__enterprise surface">
      <div>
        <p class="bill__section-eyebrow">Enterprise</p>
        <h2 class="bill__section-title">Need integrations, API access, or multi-location rollout?</h2>
        <p class="bill__section-copy">{{ planOutcomes.enterprise.summary }}</p>
      </div>
      <a :href="SITE_CONTACT_MAILTO" class="bill__cta bill__cta--ghost">Contact sales</a>
    </section>

    <section class="bill__status surface">
      <p class="bill__status-label">Payment status</p>
      <strong class="bill__status-value">{{ currentPlanLabel }}</strong>
      <p class="bill__status-sub">
        {{
          currentPlan === "free"
            ? "Free is active. Move to Core when you want quantified demand gaps and decision actions."
            : currentPlan === "core"
              ? "Core is active. Move to Pro when you want forecasts, portfolio views, and Business Health."
              : currentPlan === "pro"
                ? "Pro is active. You have the full intelligence layer."
                : "Enterprise access is active."
        }}
      </p>
      <p v-if="verifying" class="bill__note">Verifying your payment...</p>
      <p v-if="paymentMessage" class="bill__note bill__note--ok">{{ paymentMessage }}</p>
      <p v-if="paymentError" class="bill__note bill__note--err">{{ paymentError }}</p>
    </section>
  </div>
</template>

<style scoped>
.bill { display: flex; flex-direction: column; gap: 20px; }
.bill__hero,
.bill__readiness,
.bill__compare,
.bill__enterprise,
.bill__status { padding: 24px; }
.bill__hero {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, .8fr);
  gap: 20px;
  align-items: stretch;
}
.bill__hero-side {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(24, 95, 165, 0.1), rgba(83, 74, 183, 0.08));
  border: 1px solid rgba(24, 95, 165, 0.14);
}
.bill__eyebrow,
.bill__section-eyebrow,
.bill__status-label,
.bill__mini-label,
.bill__plan {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.bill__title,
.bill__section-title {
  margin-top: 8px;
  color: var(--text);
  letter-spacing: -0.04em;
}
.bill__title { font-size: clamp(28px, 4vw, 42px); line-height: 1.05; }
.bill__section-title { font-size: 24px; }
.bill__sub,
.bill__section-copy,
.bill__status-sub,
.bill__mini-copy { margin-top: 10px; color: var(--text-3); line-height: 1.6; }
.bill__hero-meta { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 14px; color: var(--text-3); }
.bill__contact-link { display: inline-block; margin-top: 14px; color: var(--blue, #185FA5); font-weight: 700; text-decoration: none; }
.bill__contact-link:hover { text-decoration: underline; }
.bill__mini-value,
.bill__status-value { display: block; margin-top: 6px; font-size: 28px; color: var(--text); }
.bill__readiness--warning { border-color: rgba(24, 95, 165, 0.14); }
.bill__readiness-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.bill__channel {
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(24, 95, 165, 0.08), rgba(24, 95, 165, 0.03));
  border: 1px solid rgba(24, 95, 165, 0.12);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bill__channel-label,
.bill__tag { font-size: 12px; color: var(--text-4); }
.bill__channel-meta { color: var(--text-3); font-size: 12px; }
.bill__issues { margin: 14px 0 0; padding-left: 18px; color: var(--text-2); display: flex; flex-direction: column; gap: 6px; }
.bill__plans {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.bill__card { padding: 22px; display: flex; flex-direction: column; gap: 12px; }
.bill__card--featured {
  border-color: rgba(24, 95, 165, 0.18);
  box-shadow: 0 14px 36px rgba(24, 95, 165, 0.10);
}
.bill__card--active { outline: 2px solid color-mix(in srgb, var(--blue, #185FA5) 22%, transparent); }
.bill__card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.bill__badge {
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(83, 74, 183, 0.12);
  color: var(--purple);
  font-size: 11px;
  font-weight: 700;
}
.bill__badge--recommended {
  background: rgba(24, 95, 165, 0.12);
  color: var(--blue, #185FA5);
}
.bill__price { font-size: 30px; color: var(--text); letter-spacing: -0.04em; }
.bill__interval { font-size: 14px; color: var(--text-4); font-weight: 600; }
.bill__desc { min-height: 72px; color: var(--text-3); line-height: 1.6; }
.bill__list { margin: 0; padding-left: 18px; color: var(--text-2); display: flex; flex-direction: column; gap: 8px; }
.bill__cta {
  margin-top: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(24, 95, 165, 0.10);
  color: var(--blue, #185FA5);
  text-decoration: none;
  font-weight: 700;
  border: 1px solid rgba(24, 95, 165, 0.12);
  cursor: pointer;
}
.bill__cta--featured {
  background: linear-gradient(135deg, #185FA5, #3B87D1);
  border-color: transparent;
  color: #fff;
}
.bill__cta--ghost {
  background: rgba(83, 74, 183, 0.08);
  border-color: rgba(83, 74, 183, 0.12);
  color: var(--purple);
}
.bill__cta--muted {
  background: color-mix(in srgb, var(--border-subtle) 92%, transparent);
  color: var(--text-3);
  cursor: default;
}
.bill__cta:disabled { opacity: .65; cursor: not-allowed; }
.bill__table {
  margin-top: 16px;
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(3, minmax(90px, 1fr));
  gap: 1px;
  background: var(--border-subtle);
  border-radius: 18px;
  overflow: hidden;
}
.bill__table-head,
.bill__table-label,
.bill__table-cell {
  background: #fff;
  padding: 14px 16px;
}
.bill__table-head { font-weight: 700; color: var(--text); }
.bill__table-label { color: var(--text-2); }
.bill__table-cell { text-align: center; color: var(--text); font-weight: 600; }
.bill__enterprise {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.bill__note { margin-top: 12px; color: var(--text-3); }
.bill__note--ok { color: var(--teal); }
.bill__note--err { color: var(--red); }
@media (max-width: 1100px) {
  .bill__hero,
  .bill__plans,
  .bill__readiness-grid,
  .bill__enterprise { grid-template-columns: 1fr; display: grid; }
}
@media (max-width: 800px) {
  .bill__table {
    grid-template-columns: minmax(150px, 1.6fr) repeat(3, minmax(70px, 1fr));
    font-size: 13px;
  }
}
</style>
