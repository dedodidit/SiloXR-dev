<script setup lang="ts">
import { formatMoney } from "../constants/markets"

definePageMeta({ auth: true })

const router = useRouter()
const route = useRoute()
const { $api } = useNuxtApp()
const { createProduct, fetchProducts, recordEvent } = useInventory()

const currentUser = useState<any | null>("current-user", () => null)
const userKey = computed(() =>
  String(currentUser.value?.id || currentUser.value?.email || "guest")
)
const { progress, load, save, reset } = useOnboardingProgress(userKey)

const saving = ref(false)
const error = ref("")
const productCreated = ref(false)

const businessOptions = [
  { value: "retail", label: "Retail" },
  { value: "pharmacy", label: "Pharmacy" },
  { value: "wholesale", label: "Wholesale" },
  { value: "other", label: "Other" },
]

const displayName = computed(() => {
  const raw = String(
    currentUser.value?.business_name
      || currentUser.value?.first_name
      || currentUser.value?.email?.split?.("@")?.[0]
      || "there"
  ).trim()
  return raw.charAt(0).toUpperCase() + raw.slice(1)
})

const activeStep = computed(() => progress.value.step)
const progressLabel = computed(() => `Step ${activeStep.value} of 3`)
const currency = computed(() => String(currentUser.value?.currency || "USD").toUpperCase())
const hasEstimatedStock = computed(() => progress.value.estimatedStock !== "" && Number(progress.value.estimatedStock) >= 0)

const insightAmount = computed(() => {
  const estimatedStock = Number(progress.value.estimatedStock || 0)
  const baselineGap = hasEstimatedStock.value ? Math.max(estimatedStock < 12 ? 120000 : 48000, 24000) : 120000
  return formatMoney(baselineGap, currency.value)
})

const insightHeadline = computed(() => {
  const productName = progress.value.productName || "this product"
  return `You may be losing ${insightAmount.value}/week from ${productName}`
})

const insightDetail = computed(() => {
  if (hasEstimatedStock.value) {
    return `Your first setup suggests ${progress.value.productName} could enter a tighter stock zone sooner than expected if demand keeps moving at the current pace.`
  }
  return `Even with one product, SiloXR can start watching for understocking patterns as you add live stock or sales activity.`
})

const insightNote = computed(() =>
  "This is an early read to help you see value immediately. It becomes more precise as you record stock updates and sales."
)

const goToStep = (step: 1 | 2 | 3) => {
  save({ step })
  error.value = ""
}

const ensureCurrentUser = async () => {
  if (currentUser.value?.id) return
  try {
    currentUser.value = await $api("/auth/me/")
  } catch {
    currentUser.value = { email: "", currency: "USD", business_name: "" }
  }
}

const persistBusinessType = async () => {
  if (!progress.value.businessType) {
    error.value = "Choose the option that best matches your business."
    return
  }

  saving.value = true
  error.value = ""
  try {
    await $api("/profile/", {
      method: "PATCH",
      body: { business_type: progress.value.businessType },
    })
    if (currentUser.value) currentUser.value.business_type = progress.value.businessType
    goToStep(2)
  } catch (err: any) {
    error.value = err?.data?.detail || "We couldn't save your business type."
  } finally {
    saving.value = false
  }
}

const buildSku = (name: string) => {
  const base = String(name || "product")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 18) || "PRODUCT"
  return `${base}-${Date.now().toString(36).toUpperCase().slice(-4)}`
}

const resolveCreatedProductId = async (created: any, sku: string) => {
  const directId = created?.id || created?.data?.id || created?.result?.id
  if (directId) return String(directId)

  const directSku = String(created?.sku || created?.data?.sku || created?.result?.sku || "").toUpperCase()
  if (directSku === sku) {
    const lookup = await fetchProducts().catch(() => null)
    const matched = lookup?.results?.find((item) => String(item.sku || "").toUpperCase() === sku)
    if (matched?.id) return String(matched.id)
  }

  const lookup = await fetchProducts().catch(() => null)
  const matched = lookup?.results?.find((item) => String(item.sku || "").toUpperCase() === sku)
  return matched?.id ? String(matched.id) : ""
}

const saveFirstProduct = async () => {
  if (!progress.value.productName.trim()) {
    error.value = "Add a product name so SiloXR has something to work with."
    return
  }

  saving.value = true
  error.value = ""

  try {
    const sku = buildSku(progress.value.productName)
    const created = await createProduct({
      name: progress.value.productName.trim(),
      sku,
      unit: "units",
      reorder_point: 0,
      reorder_quantity: 0,
    })

    const productId = await resolveCreatedProductId(created, sku)
    if (!productId) {
      throw new Error("Your product was created, but we couldn't confirm it yet. Please try again.")
    }

    if (hasEstimatedStock.value) {
      await recordEvent(productId, {
        event_type: "STOCK_COUNT",
        quantity: Number(progress.value.estimatedStock),
        verified_quantity: Number(progress.value.estimatedStock),
        notes: "First product setup",
      })
    }

    save({
      step: 3,
      productId,
      completed: true,
    })
    productCreated.value = true
  } catch (err: any) {
    error.value = err?.data?.detail || err?.data?.sku?.[0] || "We couldn't save your first product."
  } finally {
    saving.value = false
  }
}

const finishOnboarding = async () => {
  reset()
  await router.push("/dashboard")
}

onMounted(async () => {
  await ensureCurrentUser()
  load()
  if (route.query.welcome && progress.value.completed) {
    save({ completed: false, step: 1, productId: "" })
  }
})

watch(
  () => progress.value.businessType,
  (value) => save({ businessType: value })
)

watch(
  () => progress.value.productName,
  (value) => save({ productName: value })
)

watch(
  () => progress.value.estimatedStock,
  (value) => save({ estimatedStock: value })
)

useHead({ title: "Get started - SiloXR" })
</script>

<template>
  <div class="onboarding-page">
    <div class="onboarding-shell surface">
      <div class="onboarding-head">
        <div>
          <p class="onboarding-kicker">{{ progressLabel }}</p>
          <h1 class="onboarding-title">Let’s get you to value quickly, {{ displayName }}</h1>
          <p class="onboarding-subtitle">One action per screen. We’ll keep this light and get SiloXR working with your first real signal.</p>
        </div>
        <div class="onboarding-progress">
          <span v-for="item in [1, 2, 3]" :key="item" class="onboarding-progress__dot" :class="{ 'is-active': activeStep >= item }" />
        </div>
      </div>

      <Transition name="onboarding-fade" mode="out-in">
        <section v-if="activeStep === 1" key="step-1" class="onboarding-panel">
          <div class="onboarding-panel__copy">
            <p class="onboarding-panel__eyebrow">Step 1</p>
            <h2>What type of business do you run?</h2>
            <p>Choose the closest fit so SiloXR can frame your first decisions in the right operating context.</p>
          </div>

          <div class="option-grid">
            <button
              v-for="option in businessOptions"
              :key="option.value"
              type="button"
              class="option-card"
              :class="{ 'is-selected': progress.businessType === option.value }"
              @click="progress.businessType = option.value"
            >
              {{ option.label }}
            </button>
          </div>

          <p v-if="error" class="onboarding-error">{{ error }}</p>

          <div class="onboarding-actions">
            <button type="button" class="btn btn-primary" :disabled="saving" @click="persistBusinessType">
              {{ saving ? "Saving..." : "Continue" }}
            </button>
          </div>
        </section>

        <section v-else-if="activeStep === 2" key="step-2" class="onboarding-panel">
          <div class="onboarding-panel__copy">
            <p class="onboarding-panel__eyebrow">Step 2</p>
            <h2>Add one product</h2>
            <p>Start with a single product. That is enough to unlock your first decision signal.</p>
          </div>

          <div class="field-stack">
            <label class="field">
              <span class="field__label">Product name</span>
              <input
                v-model="progress.productName"
                class="field__input"
                type="text"
                placeholder="e.g. Palm oil 5L"
              />
            </label>

            <label class="field">
              <span class="field__label">Estimated stock <span class="field__optional">(optional)</span></span>
              <input
                v-model="progress.estimatedStock"
                class="field__input"
                type="number"
                min="0"
                placeholder="e.g. 24"
              />
            </label>
          </div>

          <p v-if="error" class="onboarding-error">{{ error }}</p>

          <div class="onboarding-actions">
            <button type="button" class="btn btn-secondary" @click="goToStep(1)">
              Back
            </button>
            <button type="button" class="btn btn-primary" :disabled="saving" @click="saveFirstProduct">
              {{ saving ? "Saving product..." : "Show my first insight" }}
            </button>
          </div>
        </section>

        <section v-else key="step-3" class="onboarding-panel">
          <div class="onboarding-panel__copy">
            <p class="onboarding-panel__eyebrow">Step 3</p>
            <h2>Your first insight is ready</h2>
            <p>SiloXR now has enough context to start guiding the next move. This gets sharper as you add real activity.</p>
          </div>

          <OnboardingInsightCard
            :headline="insightHeadline"
            :amount="insightAmount"
            :detail="insightDetail"
            :note="insightNote"
          />

          <div class="onboarding-success">
            <strong>{{ productCreated ? "Your first product is live." : "Your onboarding progress is saved." }}</strong>
            <span>Next, head to the dashboard to see focused workspaces and record your next stock or sales update.</span>
          </div>

          <div class="onboarding-actions">
            <button type="button" class="btn btn-secondary" @click="goToStep(2)">
              Edit product
            </button>
            <button type="button" class="btn btn-primary" @click="finishOnboarding">
              Go to dashboard
            </button>
          </div>
        </section>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.onboarding-page {
  min-height: 100vh;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--purple) 12%, transparent), transparent 34%),
    radial-gradient(circle at bottom right, color-mix(in srgb, #4AA3FF 14%, transparent), transparent 30%),
    var(--bg);
}
.onboarding-shell {
  width: min(680px, 100%);
  padding: 28px;
  border-radius: 30px;
  display: grid;
  gap: 24px;
}
.onboarding-head {
  display: grid;
  gap: 18px;
}
.onboarding-kicker,
.onboarding-panel__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #185FA5;
}
.onboarding-title {
  margin: 8px 0 0;
  font-size: clamp(28px, 5vw, 40px);
  line-height: 1.02;
  letter-spacing: -0.04em;
  color: var(--text);
}
.onboarding-subtitle,
.onboarding-panel__copy p:last-child {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-2);
}
.onboarding-progress {
  display: flex;
  gap: 8px;
}
.onboarding-progress__dot {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--border-subtle) 82%, transparent);
}
.onboarding-progress__dot.is-active {
  background: linear-gradient(135deg, #185FA5, #4AA3FF);
}
.onboarding-panel {
  display: grid;
  gap: 20px;
}
.onboarding-panel__copy h2 {
  margin: 6px 0 0;
  font-size: clamp(24px, 4vw, 32px);
  line-height: 1.06;
  letter-spacing: -0.035em;
  color: var(--text);
}
.option-grid {
  display: grid;
  gap: 12px;
}
.option-card {
  min-height: 60px;
  padding: 0 18px;
  border-radius: 18px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 96%, transparent);
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease, background .18s ease;
}
.option-card.is-selected {
  border-color: color-mix(in srgb, #185FA5 36%, var(--border-subtle));
  background: linear-gradient(145deg, color-mix(in srgb, #185FA5 12%, var(--bg-card)), color-mix(in srgb, #4AA3FF 14%, var(--bg-card)));
  box-shadow: 0 14px 28px color-mix(in srgb, #185FA5 12%, transparent);
}
.field-stack {
  display: grid;
  gap: 14px;
}
.field {
  display: grid;
  gap: 6px;
}
.field__label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-2);
}
.field__optional {
  color: var(--text-3);
}
.field__input {
  width: 100%;
  min-height: 52px;
  padding: 0 16px;
  border-radius: 18px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 96%, transparent);
  color: var(--text);
  font-size: 15px;
}
.field__input:focus {
  outline: none;
  border-color: color-mix(in srgb, #185FA5 42%, var(--border-subtle));
  box-shadow: 0 0 0 4px color-mix(in srgb, #185FA5 12%, transparent);
}
.onboarding-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.btn {
  min-height: 48px;
  padding: 0 18px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  border: 1px solid transparent;
}
.btn-primary {
  background: linear-gradient(135deg, #185FA5, #4AA3FF);
  color: #fff;
  box-shadow: 0 16px 28px color-mix(in srgb, #185FA5 18%, transparent);
}
.btn-secondary {
  background: color-mix(in srgb, var(--bg-card) 96%, transparent);
  border-color: var(--border-subtle);
  color: var(--text);
}
.btn:disabled {
  opacity: .7;
  cursor: wait;
}
.onboarding-error {
  margin: 0;
  font-size: 13px;
  color: var(--danger, #A32D2D);
}
.onboarding-success {
  display: grid;
  gap: 4px;
  padding: 16px 18px;
  border-radius: 18px;
  background: color-mix(in srgb, #0F6E56 10%, var(--bg-card));
  border: 1px solid color-mix(in srgb, #0F6E56 14%, var(--border-subtle));
}
.onboarding-success strong {
  color: var(--text);
}
.onboarding-success span {
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-2);
}
.onboarding-fade-enter-active,
.onboarding-fade-leave-active {
  transition: opacity .18s ease, transform .18s ease;
}
.onboarding-fade-enter-from,
.onboarding-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (max-width: 640px) {
  .onboarding-page {
    padding: 14px;
  }
  .onboarding-shell {
    padding: 20px;
    border-radius: 22px;
  }
  .onboarding-actions {
    flex-direction: column-reverse;
  }
  .btn {
    width: 100%;
  }
}
</style>
