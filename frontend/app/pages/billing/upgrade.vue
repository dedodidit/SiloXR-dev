<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../../constants/site"

const { $api } = useNuxtApp()
const route = useRoute()
const profile = ref<any>(null)
const plans = ref<{ key: string; label: string; interval: string; currency: string; amount_naira: number }[]>([])
const startingCheckout = ref(false)
const verifying = ref(false)
const paymentMessage = ref("")
const paymentError = ref("")

const proPlan = computed(() => plans.value.find((plan) => plan.key === "pro_monthly") ?? null)
const proPlanPriceLabel = computed(() => {
  const amount = proPlan.value?.amount_naira
  if (typeof amount !== "number") {
    return "..."
  }
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(amount)
})

const loadProfile = async () => {
  try {
    profile.value = await $api("/profile/")
  } catch {}
}

const loadPlans = async () => {
  try {
    const data = await $api<{ plans: { key: string; label: string; interval: string; currency: string; amount_naira: number }[] }>("/billing/plans/")
    plans.value = Array.isArray(data?.plans) ? data.plans : []
  } catch {}
}

const startUpgrade = async () => {
  startingCheckout.value = true
  paymentError.value = ""
  paymentMessage.value = ""

  try {
    const data = await $api<{
      authorization_url: string
    }>("/billing/paystack/initialize/", {
      method: "POST",
      body: { plan: "pro_monthly" },
    })

    if (process.client && data?.authorization_url) {
      window.location.href = data.authorization_url
    }
  } catch (e: any) {
    paymentError.value = e?.data?.detail ?? "We could not start checkout."
  } finally {
    startingCheckout.value = false
  }
}

const verifyPayment = async (reference: string) => {
  verifying.value = true
  paymentError.value = ""

  try {
    const data = await $api<{
      verified: boolean
      message: string
    }>(`/billing/paystack/verify/?reference=${encodeURIComponent(reference)}`)

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
      <h1 class="bill__title">Choose how often SiloXR works for you.</h1>
      <p class="bill__sub">
        Free users keep full product intelligence and decisions. Pro unlocks unlimited refresh frequency and higher-touch delivery.
      </p>
      <p class="bill__contact">
        Billing help:
        <a :href="SITE_CONTACT_MAILTO" class="bill__contact-link">{{ SITE_CONTACT_EMAIL }}</a>
      </p>
    </section>

    <div class="bill__grid">
      <article class="bill__card surface">
        <p class="bill__plan">Free</p>
        <h2 class="bill__price">Full access</h2>
        <p class="bill__desc">All decisions, insights, forecasts, and products. Usage is controlled by refresh cadence.</p>
        <ul class="bill__list">
          <li>Decision stack and portfolio view</li>
          <li>Telegram and email notifications</li>
          <li>Industry bootstrap from day zero</li>
        </ul>
      </article>

      <article class="bill__card bill__card--pro surface">
        <p class="bill__plan">Pro</p>
        <h2 class="bill__price">{{ proPlanPriceLabel }} / month</h2>
        <p class="bill__desc">For teams that want SiloXR running continuously instead of on a managed cadence.</p>
        <ul class="bill__list">
          <li>Unlimited refresh and decision polling</li>
          <li>WhatsApp delivery for high-confidence alerts</li>
          <li>Priority portfolio and feedback loops</li>
        </ul>
        <button class="bill__cta" :disabled="startingCheckout || verifying" @click="startUpgrade">
          {{ startingCheckout ? "Starting checkout..." : "Upgrade with Paystack" }}
        </button>
        <NuxtLink to="/profile" class="bill__link">Manage notification channels</NuxtLink>
      </article>
    </div>

    <section class="bill__status surface">
      <p class="bill__status-label">Current plan</p>
      <strong class="bill__status-value">{{ profile?.tier?.toUpperCase?.() || "FREE" }}</strong>
      <p class="bill__status-sub">
        {{ profile?.is_pro ? "Unlimited decision refresh is active." : "You still have full access. Upgrade only if you need higher frequency and premium channels." }}
      </p>
      <p v-if="verifying" class="bill__note">Verifying your Paystack payment...</p>
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
.bill__contact { margin-top: 12px; color: var(--text-3); }
.bill__contact-link { color: var(--purple); font-weight: 700; text-decoration: none; }
.bill__contact-link:hover { text-decoration: underline; }
.bill__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.bill__card { padding: 24px; display: flex; flex-direction: column; gap: 14px; }
.bill__card--pro { border-color: rgba(83,74,183,.18); box-shadow: 0 10px 30px rgba(83,74,183,.10); }
.bill__plan { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-4); }
.bill__price { font-size: 28px; letter-spacing: -0.03em; color: var(--text); }
.bill__desc { color: var(--text-3); line-height: 1.6; }
.bill__list { margin: 0; padding-left: 18px; color: var(--text-2); display: flex; flex-direction: column; gap: 8px; }
.bill__cta { margin-top: auto; display: inline-flex; align-items: center; justify-content: center; padding: 12px 14px; border-radius: 14px; background: var(--purple); color: #fff; text-decoration: none; font-weight: 700; border: none; cursor: pointer; }
.bill__cta:disabled { opacity: .65; cursor: not-allowed; }
.bill__link { color: var(--purple); font-weight: 600; text-decoration: none; }
.bill__link:hover { text-decoration: underline; }
.bill__status { padding: 20px 24px; }
.bill__status-label { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--text-4); }
.bill__status-value { display: block; margin-top: 6px; font-size: 28px; color: var(--text); }
.bill__status-sub { margin-top: 8px; color: var(--text-3); }
.bill__note { margin-top: 12px; color: var(--text-3); }
.bill__note--ok { color: var(--teal); }
.bill__note--err { color: var(--red); }
@media (max-width: 800px) {
  .bill__grid { grid-template-columns: 1fr; }
}
</style>
