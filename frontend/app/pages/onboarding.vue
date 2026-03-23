<!-- frontend/app/pages/onboarding.vue -->

<script setup lang="ts">
import type { Product } from "~/types"
import { useInventoryStore } from "~/stores/inventory"

const router = useRouter()
const store  = useInventoryStore()
const { createProduct } = useInventory()
const { recordEvent }   = useOfflineQueue()

// ── State ───────────────────────────────────────────────────────────
const step   = ref(1)
const saving = ref(false)
const error  = ref("")

const unitOptions = [
  { value: "units", label: "Units" },
  { value: "packs", label: "Packs" },
  { value: "cartons", label: "Cartons" },
  { value: "bottles", label: "Bottles" },
  { value: "bags", label: "Bags" },
  { value: "boxes", label: "Boxes" },
  { value: "crates", label: "Crates" },
  { value: "pairs", label: "Pairs" },
  { value: "kg", label: "Kilograms (kg)" },
  { value: "g", label: "Grams (g)" },
  { value: "l", label: "Litres (L)" },
  { value: "ml", label: "Millilitres (ml)" },
]

const product = reactive({
  name: "",
  sku: "",
  unit: "units",
  reorder_point: 0,
  reorder_quantity: 0,
})

const stockCount     = ref<number | null>(null)
const createdProduct = ref<Product | null>(null)
const selectedUnitLabel = computed(
  () => unitOptions.find((option) => option.value === product.unit)?.label ?? product.unit
)

// ── Helpers ─────────────────────────────────────────────────────────
const resetError = () => (error.value = "")

// Handles all API response shapes
const extractProduct = (res: any): Product | null => {
  if (res?.id) return res
  if (res?.data?.id) return res.data
  if (res?.sku) return res // fallback (no id case)
  return null
}

// ── Step 1: Create product ──────────────────────────────────────────
const saveProduct = async () => {
  resetError()

  if (!product.name || !product.sku) {
    error.value = "Product name and SKU are required."
    return
  }

  saving.value = true

  try {
    const res = await createProduct({ ...product })

    console.log("CREATE PRODUCT RESPONSE:", res)

    const parsed = extractProduct(res)

    if (!parsed) {
      throw new Error("Product created but could not resolve it.")
    }

    // 🔥 Critical fix: recover ID if missing
    if (!parsed.id) {
      console.warn("Missing ID, attempting recovery...")

      await store.load()

      const found = store.products?.find(
        (p: any) => p.sku === product.sku
      )

      if (!found?.id) {
        throw new Error("Product created but ID could not be recovered.")
      }

      createdProduct.value = found
    } else {
      createdProduct.value = parsed
    }

    step.value = 2

  } catch (e: any) {
    console.error("CREATE PRODUCT ERROR:", e)

    error.value =
      e?.data?.sku?.[0] ||
      e?.data?.detail ||
      e?.message ||
      "Could not save product."

  } finally {
    saving.value = false
  }
}

// ── Step 2: Record stock ────────────────────────────────────────────
const saveStockCount = async () => {
  resetError()

  if (stockCount.value == null || stockCount.value < 0) {
    error.value = "Enter a valid stock quantity."
    return
  }

  if (!createdProduct.value?.id) {
    error.value = "Product not initialized correctly."
    return
  }

  saving.value = true

  try {
    await recordEvent(createdProduct.value.id, {
      event_type: "STOCK_COUNT",
      quantity: stockCount.value,
      verified_quantity: stockCount.value,
      notes: "Opening stock count (onboarding)",
    })

    await store.load()
    step.value = 3

  } catch (e: any) {
    console.error("STOCK COUNT ERROR:", e)

    error.value =
      e?.response?._data?.detail ||
      e?.data?.detail ||
      "Could not record stock count."

  } finally {
    saving.value = false
  }
}

// ── Reset ───────────────────────────────────────────────────────────
const addAnother = () => {
  step.value = 1

  Object.assign(product, {
    name: "",
    sku: "",
    unit: "units",
    reorder_point: 0,
    reorder_quantity: 0,
  })

  stockCount.value = null
  createdProduct.value = null
  resetError()
}
</script>
<template>
  <div class="onboard-page">
    <div class="onboard-card surface">

      <!-- Progress -->
      <div class="onboard-steps">
        <div class="onboard-step" :class="{ active: step >= 1, done: step > 1 }">
          <span class="onboard-step__num">1</span>
          <span>Product details</span>
        </div>
        <div class="onboard-step__line" />
        <div class="onboard-step" :class="{ active: step >= 2, done: step > 2 }">
          <span class="onboard-step__num">2</span>
          <span>Opening stock</span>
        </div>
        <div class="onboard-step__line" />
        <div class="onboard-step" :class="{ active: step >= 3 }">
          <span class="onboard-step__num">3</span>
          <span>Done</span>
        </div>
      </div>

      <!-- Step 1: Product details -->
      <template v-if="step === 1">
        <h2 class="onboard-card__title">Add your first product</h2>
        <p class="onboard-card__sub">
          Start with one product. You can add more any time.
        </p>
        <form class="onboard-form" @submit.prevent="saveProduct">
          <div class="field-row">
            <div class="field">
              <label class="field__label">Product name</label>
              <input v-model="product.name" class="field__input"
                type="text" placeholder="e.g. Palm oil 5L" required />
            </div>
            <div class="field">
              <label class="field__label">SKU / code</label>
              <input v-model="product.sku" class="field__input"
                type="text" placeholder="e.g. PO-5L-001" required />
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label class="field__label">Unit of measure</label>
              <select v-model="product.unit" class="field__input">
                <option
                  v-for="option in unitOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
              <span class="field__hint">Choose the unit you physically count for this product.</span>
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label class="field__label">Reorder point</label>
              <input v-model.number="product.reorder_point" class="field__input"
                type="number" min="0" placeholder="e.g. 20" />
            </div>
            <div class="field">
              <label class="field__label">Reorder quantity</label>
              <input v-model.number="product.reorder_quantity" class="field__input"
                type="number" min="0" placeholder="e.g. 100" />
            </div>
          </div>
          <p v-if="error" class="onboard-error">{{ error }}</p>
          <button type="submit" class="onboard-btn" :disabled="saving">
            {{ saving ? "Saving…" : "Continue" }}
          </button>
        </form>
      </template>

      <!-- Step 2: Opening stock count -->
      <template v-if="step === 2">
        <h2 class="onboard-card__title">How many do you have right now?</h2>
        <p class="onboard-card__sub">
          Count your current stock of
          <strong>{{ createdProduct?.name }}</strong>.
          This is your verified baseline — the system learns from here.
        </p>
        <form class="onboard-form" @submit.prevent="saveStockCount">
          <div class="field">
            <label class="field__label">
              Current quantity ({{ selectedUnitLabel }})
            </label>
            <input v-model.number="stockCount" class="field__input field__input--lg"
              type="number" min="0" required placeholder="0" />
          </div>
          <p v-if="error" class="onboard-error">{{ error }}</p>
          <button type="submit" class="onboard-btn" :disabled="saving">
            {{ saving ? "Recording…" : "Record stock count" }}
          </button>
        </form>
      </template>

      <!-- Step 3: Done -->
      <template v-if="step === 3">
        <div class="onboard-done">
          <div class="onboard-done__icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="22" stroke="#0F6E56" stroke-width="2"/>
              <path d="M15 24l7 7 11-14" stroke="#0F6E56" stroke-width="2.5"
                stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <h2 class="onboard-card__title">
            {{ createdProduct?.name }} is ready
          </h2>
          <p class="onboard-card__sub">
            SiloXR is now learning your consumption patterns.
            Decisions and forecasts will appear within 24 hours as you record sales.
          </p>
          <div class="onboard-done__actions">
            <button class="onboard-btn onboard-btn--secondary" @click="addAnother">
              Add another product
            </button>
          <button class="onboard-btn" @click="router.push('/dashboard')">
            Go to dashboard
          </button>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<style scoped>
.onboard-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;background:var(--color-bg)}
.onboard-card{width:100%;max-width:540px;padding:36px 32px;display:flex;flex-direction:column;gap:24px}
.onboard-steps{display:flex;align-items:center;gap:0;margin-bottom:8px}
.onboard-step{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--color-text-hint);font-weight:500;white-space:nowrap}
.onboard-step.active{color:var(--color-purple)}
.onboard-step.done{color:var(--color-teal)}
.onboard-step__num{width:22px;height:22px;border-radius:50%;border:1.5px solid currentColor;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.onboard-step__line{flex:1;height:1px;background:var(--color-border);margin:0 8px}
.onboard-card__title{font-size:18px;font-weight:600;color:var(--color-text)}
.onboard-card__sub{font-size:13px;color:var(--color-text-muted);line-height:1.6}
.onboard-form{display:flex;flex-direction:column;gap:14px}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field{display:flex;flex-direction:column;gap:5px}
.field__label{font-size:12px;font-weight:600;color:var(--color-text-muted)}
.field__hint{font-size:12px;color:var(--color-text-hint);line-height:1.45}
.field__input{padding:10px 14px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);color:var(--color-text);font-size:14px;font-family:var(--font-sans);width:100%;transition:border-color .15s}
.field__input:focus{outline:none;border-color:var(--color-purple)}
.field__input--lg{font-size:28px;font-weight:700;text-align:center;padding:16px}
.onboard-error{font-size:13px;color:var(--color-red);padding:8px 12px;background:var(--color-red-light);border-radius:var(--radius-sm)}
.onboard-btn{padding:12px 24px;background:var(--color-purple);color:#fff;border:none;border-radius:var(--radius-md);font-size:14px;font-weight:600;cursor:pointer;transition:opacity .15s}
.onboard-btn:hover:not(:disabled){opacity:.88}
.onboard-btn:disabled{opacity:.55;cursor:not-allowed}
.onboard-btn--secondary{background:transparent;border:1px solid var(--color-border);color:var(--color-text-muted)}
.onboard-btn--secondary:hover{border-color:var(--color-purple);color:var(--color-purple)}
.onboard-done{display:flex;flex-direction:column;align-items:center;gap:16px;text-align:center;padding:16px 0}
.onboard-done__icon{margin-bottom:4px}
.onboard-done__actions{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-top:8px}
</style>
