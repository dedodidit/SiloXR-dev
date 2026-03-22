<!-- frontend/app/pages/products/[id].vue -->

<script setup lang="ts">
import { useInventoryStore } from "~/stores/inventory"

const route  = useRoute()
const router = useRouter()
const store  = useInventoryStore()
const { fetchForecastStrip } = useDecisions()
const { recordEvent } = useOfflineQueue()

const product      = ref<any>(null)
const forecastStrip = ref([])
const showEventForm = ref(false)
const loading       = ref(true)
const saving        = ref(false)
const error         = ref("")

const eventForm = reactive({
  event_type:        "SALE",
  quantity:          1,
  verified_quantity: 0,
  notes:             "",
})

// at the top of onMounted in products/[id].vue
onMounted(async () => {
  const id = route.params.id as string

  if (!id || id === "undefined") {
    router.push("/dashboard")
    return
  }

  await store.select(id)
  product.value = store.selected

  if (product.value) {
    forecastStrip.value = await fetchForecastStrip(product.value.id, 7).catch(() => [])
  }

  loading.value = false
})


const submitEvent = async () => {
  error.value  = ""
  saving.value = true
  try {
    const payload: any = {
      event_type: eventForm.event_type,
      quantity:   eventForm.quantity,
      notes:      eventForm.notes,
      occurred_at: new Date().toISOString(),
    }
    if (eventForm.event_type === "STOCK_COUNT") {
      payload.verified_quantity = eventForm.verified_quantity
      payload.quantity = 0
    }
    await recordEvent(product.value.id, payload)
    // Refresh product
    await store.select(product.value.id)
    product.value     = store.selected
    forecastStrip.value = await fetchForecastStrip(product.value.id, 7).catch(() => [])
    showEventForm.value = false
    Object.assign(eventForm, { event_type:"SALE", quantity:1, verified_quantity:0, notes:"" })
  } catch (e: any) {
    error.value = e?.data?.detail ?? "Could not record event."
  } finally {
    saving.value = false
  }
}

const eventTypeLabels: Record<string, string> = {
  SALE: "Sale", RESTOCK: "Restock", STOCK_COUNT: "Stock count",
  ADJUSTMENT: "Adjustment", WASTE: "Waste",
}
</script>

<template>
  <div class="product-page">

    <div v-if="loading" class="product-page__loading">Loading product…</div>

    <template v-else-if="product">
      <!-- Header -->
      <div class="product-page__header">
        <button class="product-page__back" @click="router.push('/dashboard')">
          ← Dashboard
        </button>
        <div>
          <h1 class="product-page__title">{{ product.name }}</h1>
          <span class="product-page__sku">{{ product.sku }}</span>
        </div>
        <button class="product-page__add-btn" @click="showEventForm = !showEventForm">
          {{ showEventForm ? 'Cancel' : '+ Record event' }}
        </button>
      </div>

      <!-- Stat strip -->
      <div class="product-page__stats">
        <div class="pstat">
          <span class="pstat__val">{{ product.last_verified_quantity }}</span>
          <span class="pstat__label">Verified stock</span>
        </div>
        <div class="pstat">
          <span class="pstat__val">~{{ Math.round(product.estimated_quantity) }}</span>
          <span class="pstat__label">Estimated stock</span>
        </div>
        <div class="pstat">
          <span class="pstat__val">
            {{ product.days_remaining != null ? `~${Math.round(product.days_remaining)}d` : '—' }}
          </span>
          <span class="pstat__label">Days remaining</span>
        </div>
        <div class="pstat">
          <ConfidenceBadge :score="product.confidence_score" />
          <span class="pstat__label">Confidence</span>
        </div>
      </div>

      <!-- Event recording form -->
      <div v-if="showEventForm" class="product-page__event-form surface">
        <h3 class="product-page__form-title">Record an event</h3>
        <form @submit.prevent="submitEvent" class="event-form">
          <div class="field-row">
            <div class="field">
              <label class="field__label">Event type</label>
              <select v-model="eventForm.event_type" class="field__input">
                <option v-for="(label, val) in eventTypeLabels" :key="val" :value="val">
                  {{ label }}
                </option>
              </select>
            </div>
            <div class="field" v-if="eventForm.event_type !== 'STOCK_COUNT'">
              <label class="field__label">Quantity ({{ product.unit }})</label>
              <input v-model.number="eventForm.quantity" class="field__input"
                type="number" min="0.01" step="0.01" required />
            </div>
            <div class="field" v-else>
              <label class="field__label">Counted quantity ({{ product.unit }})</label>
              <input v-model.number="eventForm.verified_quantity" class="field__input"
                type="number" min="0" required />
            </div>
          </div>
          <div class="field">
            <label class="field__label">Notes (optional)</label>
            <input v-model="eventForm.notes" class="field__input"
              type="text" placeholder="Any context…" />
          </div>
          <p v-if="error" class="onboard-error">{{ error }}</p>
          <button type="submit" class="onboard-btn" :disabled="saving">
            {{ saving ? "Saving…" : "Record event" }}
          </button>
        </form>
      </div>

      <!-- Active decision -->
      <div v-if="product.active_decision" class="product-page__section">
        <h2 class="product-page__section-title">Active decision</h2>
        <DecisionCard :decision="product.active_decision" />
      </div>

      <div class="product-page__section">
        <h2 class="product-page__section-title">Sales forecast</h2>
        <SalesForecastChart :burn-rate="product.burn_rate" :recent-events="product.recent_events" />
      </div>

      <!-- Forecast strip -->
      <div v-if="forecastStrip.length" class="product-page__section">
        <h2 class="product-page__section-title">Stock projection</h2>
        <ForecastStrip
          :strips="forecastStrip"
          :max-quantity="product.estimated_quantity"
          :current-quantity="product.estimated_quantity"
          :recent-events="product.recent_events"
        />
      </div>

      <!-- Trend chart -->
      <div v-if="forecastStrip.length" class="product-page__section">
        <h2 class="product-page__section-title">Stock trend</h2>
        <TrendChart
          :product-id="product.id"
          :product-name="product.name"
          :current-quantity="product.estimated_quantity"
          :reorder-point="product.reorder_point"
          :forecast-strip="forecastStrip"
        />
      </div>

    </template>

    <div v-else class="product-page__loading">Product not found.</div>
  </div>
</template>

<style scoped>
.product-page{max-width:900px;margin:0 auto;padding:24px 16px 80px;display:flex;flex-direction:column;gap:24px}
.product-page__loading{padding:60px;text-align:center;color:var(--color-text-hint);font-size:14px}
.product-page__header{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.product-page__back{font-size:13px;color:var(--color-text-muted);background:none;border:none;cursor:pointer;padding:0}
.product-page__back:hover{color:var(--color-purple)}
.product-page__title{font-size:20px;font-weight:600;color:var(--color-text)}
.product-page__sku{font-size:12px;color:var(--color-text-hint)}
.product-page__add-btn{margin-left:auto;padding:8px 16px;background:var(--color-purple);color:#fff;border:none;border-radius:var(--radius-md);font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s}
.product-page__add-btn:hover{opacity:.88}
.product-page__stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(max-width:600px){.product-page__stats{grid-template-columns:repeat(2,1fr)}}
.pstat{background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:14px 16px;display:flex;flex-direction:column;gap:4px}
.pstat__val{font-size:20px;font-weight:700;color:var(--color-text);line-height:1}
.pstat__label{font-size:11px;color:var(--color-text-hint)}
.product-page__event-form{padding:20px 24px;display:flex;flex-direction:column;gap:16px}
.product-page__form-title{font-size:14px;font-weight:600;color:var(--color-text)}
.event-form{display:flex;flex-direction:column;gap:12px}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field{display:flex;flex-direction:column;gap:5px}
.field__label{font-size:12px;font-weight:600;color:var(--color-text-muted)}
.field__input{padding:9px 12px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);color:var(--color-text);font-size:13px;font-family:var(--font-sans);width:100%}
.field__input:focus{outline:none;border-color:var(--color-purple)}
.onboard-error{font-size:13px;color:var(--color-red);padding:8px 12px;background:var(--color-red-light);border-radius:var(--radius-sm)}
.onboard-btn{padding:10px 20px;background:var(--color-purple);color:#fff;border:none;border-radius:var(--radius-md);font-size:13px;font-weight:600;cursor:pointer;align-self:flex-start}
.onboard-btn:disabled{opacity:.55;cursor:not-allowed}
.product-page__section{display:flex;flex-direction:column;gap:12px}
.product-page__section-title{font-size:14px;font-weight:600;color:var(--color-text)}
</style>
