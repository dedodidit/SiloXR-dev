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

const profile = ref<any>(null)
const plans = ref<BillingPlan[]>([])
const pricingCountry = ref("")
const pricingCurrency = ref("USD")
const startingCheckout = ref("")
const verifying = ref(false)
const paymentMessage = ref("")
const paymentError = ref("")

const featureMap: Record<string, string[]> = {
  free: [
    "Create products, stock counts, and sales records",
    "Basic operational signals without quantified revenue views",
    "Start with a free business workspace",
  ],
  core: [
    "Revenue gap values and product-level demand gaps",
    "Basic prioritization with clear actions",
    "Decision layer access without forecast bands",
  ],
  pro: [
    "Forecasting, trends, and confidence bands",
    "Business Health and portfolio-level insights",
    "Advanced intelligence layer access",
  ],
  enterprise: [
    "Integrations and API access",
    "Multi-location support",
    "Contact-sales onboarding and custom rollout",
  ],
}

const currentPlan = computed(() => String(profile.value?.tier || "free").toLowerCase())

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
    await loadProfile()
  } catch (e: any) {
    paymentError.value = e?.data?.detail ?? "We could not confirm the payment yet."
  } finally {
    verifying.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadProfile(), loadPlans()])

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
      <p class="bill__eyebrow">Billing</p>
      <h1 class="bill__title">Choose the decision layer that fits your business.</h1>
      <p class="bill__sub">
        Pricing is localized by market tier with safe defaults. Start free, move into Core for quantified decision support, or unlock the full intelligence layer with Pro.
      </p>
      <p class="bill__contact">
        Billing help:
        <a :href="SITE_CONTACT_MAILTO" class="bill__contact-link">{{ SITE_CONTACT_EMAIL }}</a>
      </p>
      <p class="bill__context">
        Market: <strong>{{ pricingCountry || "Default tier" }}</strong>
        <span>·</span>
        Currency: <strong>{{ pricingCurrency }}</strong>
      </p>
    </section>

    <div class="bill__grid">
      <article
        v-for="plan in sortedPlans"
        :key="plan.key"
        class="bill__card surface"
        :class="{
          'bill__card--featured': plan.label.toLowerCase() === 'pro',
          'bill__card--active': currentPlan === plan.label.toLowerCase(),
        }"
      >
        <div class="bill__card-top">
          <p class="bill__plan">{{ plan.label }}</p>
          <span v-if="currentPlan === plan.label.toLowerCase()" class="bill__badge">Current</span>
        </div>

        <h2 class="bill__price">
          {{ formatPrice(plan) }}
          <span v-if="plan.amount != null" class="bill__interval">/ {{ plan.interval }}</span>
        </h2>

        <p class="bill__desc">
          Tier {{ plan.pricing_tier }} pricing in {{ plan.currency }}.
          <span v-if="plan.amount_usd_reference != null">Based on a {{ plan.amount_usd_reference }} USD reference.</span>
        </p>

        <ul class="bill__list">
          <li v-for="item in featureMap[plan.label.toLowerCase()] || []" :key="item">{{ item }}</li>
        </ul>

        <button
          v-if="plan.label.toLowerCase() === 'core' || plan.label.toLowerCase() === 'pro'"
          class="bill__cta"
          :disabled="startingCheckout === plan.key || verifying || currentPlan === plan.label.toLowerCase()"
          @click="startCheckout(plan.key)"
        >
          {{
            currentPlan === plan.label.toLowerCase()
              ? "Current plan"
              : startingCheckout === plan.key
                ? "Starting checkout..."
                : `Upgrade to ${plan.label}`
          }}
        </button>

        <a
          v-else-if="plan.contact_sales"
          :href="SITE_CONTACT_MAILTO"
          class="bill__cta bill__cta--ghost"
        >
          Contact sales
        </a>

        <span v-else class="bill__cta bill__cta--muted">Included</span>
      </article>
    </div>

    <section class="bill__status surface">
      <p class="bill__status-label">Current plan</p>
      <strong class="bill__status-value">{{ currentPlan.toUpperCase() }}</strong>
      <p class="bill__status-sub">
        {{
          currentPlan === "free"
            ? "Free includes the data layer and basic signals. Upgrade when you need quantified decisions or the intelligence layer."
            : currentPlan === "core"
              ? "Core is active. Quantified decision support is available for your business."
              : currentPlan === "pro"
                ? "Pro is active. Forecasting, business health, and portfolio intelligence are available."
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
.bill { display: flex; flex-direction: column; gap: 24px; }
.bill__hero { padding: 28px; }
.bill__eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-4); }
.bill__title { margin-top: 8px; font-size: clamp(28px, 5vw, 44px); line-height: 1.05; letter-spacing: -0.04em; color: var(--text); }
.bill__sub { margin-top: 10px; max-width: 760px; color: var(--text-3); line-height: 1.6; }
.bill__contact, .bill__context { margin-top: 12px; color: var(--text-3); }
.bill__context { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.bill__contact-link { color: var(--purple); font-weight: 700; text-decoration: none; }
.bill__contact-link:hover { text-decoration: underline; }
.bill__grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
.bill__card { padding: 24px; display: flex; flex-direction: column; gap: 14px; }
.bill__card--featured { border-color: rgba(83,74,183,.22); box-shadow: 0 10px 30px rgba(83,74,183,.10); }
.bill__card--active { outline: 2px solid color-mix(in srgb, var(--purple) 28%, transparent); }
.bill__card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.bill__badge { padding: 5px 9px; border-radius: 999px; background: color-mix(in srgb, var(--purple) 12%, transparent); color: var(--purple); font-size: 11px; font-weight: 700; }
.bill__plan { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-4); }
.bill__price { font-size: 28px; letter-spacing: -0.03em; color: var(--text); }
.bill__interval { font-size: 14px; color: var(--text-4); font-weight: 600; }
.bill__desc { color: var(--text-3); line-height: 1.6; min-height: 66px; }
.bill__list { margin: 0; padding-left: 18px; color: var(--text-2); display: flex; flex-direction: column; gap: 8px; }
.bill__cta { margin-top: auto; display: inline-flex; align-items: center; justify-content: center; padding: 12px 14px; border-radius: 14px; background: var(--purple); color: #fff; text-decoration: none; font-weight: 700; border: none; cursor: pointer; }
.bill__cta:disabled { opacity: .65; cursor: not-allowed; }
.bill__cta--ghost { background: color-mix(in srgb, var(--purple) 12%, transparent); color: var(--purple); }
.bill__cta--muted { background: color-mix(in srgb, var(--border-subtle) 90%, transparent); color: var(--text-3); cursor: default; }
.bill__status { padding: 20px 24px; }
.bill__status-label { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-4); }
.bill__status-value { display: block; margin-top: 6px; font-size: 28px; color: var(--text); }
.bill__status-sub { margin-top: 8px; color: var(--text-3); }
.bill__note { margin-top: 12px; color: var(--text-3); }
.bill__note--ok { color: var(--teal); }
.bill__note--err { color: var(--red); }
@media (max-width: 1100px) {
  .bill__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 800px) {
  .bill__grid { grid-template-columns: 1fr; }
}
</style>
