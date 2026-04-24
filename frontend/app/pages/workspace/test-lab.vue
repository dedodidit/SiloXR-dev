<script setup lang="ts">
import type { DecisionSimulationResponse, ForecastStrip, InventoryEventCreate, Product } from "~/types"

definePageMeta({ auth: true })

const inventoryStore = useInventoryStore()
const { summary } = useDashboard()
const { fetchProducts, fetchProduct, createProduct, updateProduct, recordEvent } = useInventory()
const { fetchForecastStrip, fetchDecisionSimulation } = useDecisions()

type ScenarioEventDraft = {
  id: string
  event_type: "SALE" | "RESTOCK" | "STOCK_COUNT"
  quantity: number
  verified_quantity: number
  occurred_at: string
  notes: string
}

const selectedProductId = ref("")
const productSnapshot = ref<Product | null>(null)
const forecastStrip = ref<ForecastStrip[]>([])
const decisionSimulation = ref<DecisionSimulationResponse | null>(null)
const runningScenario = ref(false)
const savingProduct = ref(false)
const loadingCatalog = ref(false)
const syncingOutput = ref(false)
const compareMode = ref<"baseline" | "live" | "mixed">("mixed")
const error = ref("")
const statusNote = ref("")
const activityLog = ref<string[]>([])

const productDraft = reactive({
  name: "",
  sku: "",
  unit: "units",
  reorder_point: 5,
  reorder_quantity: 20,
  opening_stock: 12,
})

const toLocalDateTime = (date = new Date()) => {
  const pad = (value: number) => String(value).padStart(2, "0")
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return `${shifted.getFullYear()}-${pad(shifted.getMonth() + 1)}-${pad(shifted.getDate())}T${pad(shifted.getHours())}:${pad(shifted.getMinutes())}`
}

const newDraftEvent = (event_type: ScenarioEventDraft["event_type"]): ScenarioEventDraft => ({
  id: crypto.randomUUID(),
  event_type,
  quantity: event_type === "STOCK_COUNT" ? 0 : 1,
  verified_quantity: event_type === "STOCK_COUNT" ? 12 : 0,
  occurred_at: toLocalDateTime(),
  notes: event_type === "SALE" ? "Scenario sale" : event_type === "RESTOCK" ? "Scenario restock" : "Scenario count",
})

const scenarioEvents = ref<ScenarioEventDraft[]>([
  newDraftEvent("STOCK_COUNT"),
  newDraftEvent("SALE"),
])

const buildSku = (name: string) => {
  const base = String(name || "product")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 18) || "PRODUCT"
  return `${base}-${Date.now().toString(36).toUpperCase().slice(-4)}`
}

const isBaselineActive = computed(() => Boolean(summary.value?.baseline_in_use))
const operatingAssumption = computed(() => String(summary.value?.operating_assumption || "").trim())
const recentEvents = computed(() => productSnapshot.value?.recent_events ?? [])
const selectedProduct = computed(() => {
  if (productSnapshot.value?.id) return productSnapshot.value
  if (!selectedProductId.value) return null
  return inventoryStore.products.find((product) => product.id === selectedProductId.value) ?? null
})

const currentMode = computed(() => {
  if (compareMode.value === "baseline") return "baseline-only"
  if (compareMode.value === "live") return "live-data-only"
  if (isBaselineActive.value && recentEvents.value.length === 0) return "industry baseline"
  if (Number(selectedProduct.value?.confidence_score ?? 0) >= 0.6) return "live signal"
  if (recentEvents.value.length > 0) return "mixed signal"
  return "new scenario"
})

const modeCopy = computed(() => {
  if (compareMode.value === "baseline") {
    return "Create or pick a product, then run it without any inventory events to see the baseline-driven output."
  }
  if (compareMode.value === "live") {
    return "Use your drafted sales and stock events only, without the extra opening-stock bootstrap."
  }
  return "Use opening stock plus your drafted events so you can see the hybrid baseline-to-live transition."
})

const currentHeadline = computed(() => {
  if (!selectedProduct.value) return "Create or pick a product, then run it through the live system"
  if (selectedProduct.value.active_decision?.action) {
    return `${selectedProduct.value.name} is producing a ${selectedProduct.value.active_decision.action} outcome`
  }
  return `${selectedProduct.value.name} is ready for the next test`
})

const productStats = computed(() => {
  const product = selectedProduct.value
  return [
    {
      label: "Estimated stock",
      value: product ? `~${Math.round(Number(product.estimated_quantity ?? 0))}` : "n/a",
      hint: product ? "Live quantity after the latest run" : "Create a product to see the estimate",
    },
    {
      label: "Days remaining",
      value: product?.days_remaining != null ? `~${Math.max(1, Math.round(Number(product.days_remaining ?? 0)))}d` : "n/a",
      hint: product ? "Projected from current demand" : "Run a scenario to generate a projection",
    },
    {
      label: "Confidence",
      value: product ? `${Math.round(Number(product.confidence_score ?? 0) * 100)}%` : "n/a",
      hint: product ? "How much the system trusts the signal" : "No operating signal yet",
    },
    {
      label: "Data source",
      value: currentMode.value,
      hint: isBaselineActive.value ? "Industry data is still helping bootstrap the model" : "Using product history only",
    },
  ]
})

const resetDraftFromProduct = (product: Product | null) => {
  productDraft.name = product?.name ?? "Sandbox product"
  productDraft.sku = product?.sku ?? buildSku(product?.name ?? "sandbox product")
  productDraft.unit = product?.unit ?? "units"
  productDraft.reorder_point = Math.max(0, Math.round(Number(product?.reorder_point ?? 5)))
  productDraft.reorder_quantity = Math.max(0, Math.round(Number(product?.reorder_quantity ?? 20)))
  productDraft.opening_stock = Math.max(0, Math.round(Number(product?.last_verified_quantity ?? product?.estimated_quantity ?? 12)))
}

const log = (message: string) => {
  activityLog.value.unshift(`${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ${message}`)
  activityLog.value = activityLog.value.slice(0, 8)
}

const resolveCreatedProductId = async (created: any, sku: string) => {
  const directId = created?.id || created?.data?.id || created?.result?.id
  if (directId) return String(directId)

  const lookup = await fetchProducts().catch(() => null)
  const matched = lookup?.results?.find((item) => String(item.sku || "").toUpperCase() === sku)
  return matched?.id ? String(matched.id) : ""
}

const refreshProductContext = async (productId: string) => {
  if (!productId) {
    productSnapshot.value = null
    forecastStrip.value = []
    decisionSimulation.value = null
    return
  }

  syncingOutput.value = true
  error.value = ""
  try {
    const product = await fetchProduct(productId)
    productSnapshot.value = product
    inventoryStore.upsert(product)
    forecastStrip.value = await fetchForecastStrip(productId, 7).catch(() => [])
    if (product.active_decision?.id) {
      decisionSimulation.value = await fetchDecisionSimulation(product.active_decision.id).catch(() => null)
    } else {
      decisionSimulation.value = null
    }
    log(`Loaded ${product.name} from the live system.`)
  } catch (err: any) {
    error.value = err?.data?.detail || "Could not load the product context."
  } finally {
    syncingOutput.value = false
  }
}

const saveProductProfile = async () => {
  const name = String(productDraft.name || "").trim()
  if (!name) {
    error.value = "Add a product name first."
    return ""
  }

  savingProduct.value = true
  error.value = ""
  try {
    const payload = {
      name,
      sku: String(productDraft.sku || "").trim() || buildSku(name),
      unit: String(productDraft.unit || "units").trim() || "units",
      reorder_point: Math.max(0, Math.round(Number(productDraft.reorder_point ?? 0))),
      reorder_quantity: Math.max(0, Math.round(Number(productDraft.reorder_quantity ?? 0))),
    }

    const existingId = selectedProductId.value || productSnapshot.value?.id || ""
    let saved: Product

    if (existingId) {
      saved = await updateProduct(existingId, payload)
      log(`Updated ${saved.name}.`)
    } else {
      saved = await createProduct(payload)
      const resolvedId = await resolveCreatedProductId(saved, payload.sku.toUpperCase())
      if (resolvedId) {
        selectedProductId.value = resolvedId
        saved = await fetchProduct(resolvedId).catch(() => saved)
      }
      log(`Created ${saved.name}.`)
    }

    inventoryStore.upsert(saved)
    productSnapshot.value = saved
    selectedProductId.value = saved.id
    resetDraftFromProduct(saved)
    statusNote.value = `Product saved: ${saved.name}.`
    return saved.id
  } catch (err: any) {
    error.value = err?.data?.detail || err?.data?.sku?.[0] || "Could not save the product profile."
    return ""
  } finally {
    savingProduct.value = false
  }
}

const addEventDraft = (event_type: ScenarioEventDraft["event_type"]) => {
  scenarioEvents.value.push(newDraftEvent(event_type))
}

const removeEventDraft = (id: string) => {
  scenarioEvents.value = scenarioEvents.value.filter((event) => event.id !== id)
}

const clearActivityLog = () => {
  activityLog.value = []
}

const buildScenarioEvents = () => {
  if (compareMode.value === "baseline") return []

  const openingStock = Math.max(0, Math.round(Number(productDraft.opening_stock ?? 0)))
  const items = scenarioEvents.value.map((event) => ({ ...event }))
  const stockCountIndex = items.findIndex((event) => event.event_type === "STOCK_COUNT")

  if (compareMode.value === "mixed" && openingStock > 0) {
    if (stockCountIndex >= 0) {
      items[stockCountIndex].verified_quantity = openingStock
      items[stockCountIndex].notes = items[stockCountIndex].notes || "Opening stock from test lab"
    } else {
      items.unshift({
        ...newDraftEvent("STOCK_COUNT"),
        verified_quantity: openingStock,
        notes: "Opening stock from test lab",
      })
    }
  }

  return items
}

const runScenario = async () => {
  error.value = ""
  statusNote.value = ""
  const productId = await saveProductProfile()
  if (!productId) return
  const events = buildScenarioEvents()
  if (compareMode.value !== "baseline" && !events.length) {
    error.value = "Add at least one event before running the scenario."
    return
  }

  runningScenario.value = true
  try {
    for (const draft of events) {
      const event: InventoryEventCreate = {
        event_type: draft.event_type,
        quantity: draft.event_type === "STOCK_COUNT" ? 0 : Math.max(0, Number(draft.quantity ?? 0)),
        occurred_at: new Date(draft.occurred_at || Date.now()).toISOString(),
        notes: draft.notes.trim() || undefined,
      }

      if (draft.event_type === "STOCK_COUNT") {
        event.verified_quantity = Math.max(0, Math.round(Number(draft.verified_quantity ?? 0)))
      }

      await recordEvent(productId, event)
      log(`Recorded ${draft.event_type.toLowerCase()} for ${productDraft.name}.`)
    }

    await refreshProductContext(productId)
    statusNote.value =
      compareMode.value === "baseline"
        ? "Ran a baseline-only probe with no direct inventory events."
        : `Ran ${events.length} event(s) through the live system.`
  } catch (err: any) {
    error.value = err?.data?.detail || "Could not run the scenario."
  } finally {
    runningScenario.value = false
  }
}

watch(
  selectedProductId,
  async (id) => {
    if (!id) {
      productSnapshot.value = null
      forecastStrip.value = []
      decisionSimulation.value = null
      resetDraftFromProduct(null)
      return
    }

    await refreshProductContext(id)
    if (productSnapshot.value) {
      resetDraftFromProduct(productSnapshot.value)
    }
  },
  { immediate: true },
)

onMounted(async () => {
  loadingCatalog.value = true
  try {
    await inventoryStore.load()
  } catch (err: any) {
    error.value = err?.data?.detail || "Could not load the product catalog."
  } finally {
    loadingCatalog.value = false
  }
})

useHead({ title: "Test lab - SiloXR" })
</script>

<template>
  <div class="test-lab">
    <header class="test-lab__hero surface">
      <div>
        <p class="test-lab__eyebrow">Admin test lab</p>
        <h1 class="test-lab__title">Push data in, run the live system, and inspect the prediction immediately.</h1>
        <p class="test-lab__copy">
          This page uses the same backend paths as the main product flow, so you can create a sandbox product, replay events, and see the forecast and decision output in one place.
        </p>
      </div>
      <div class="test-lab__hero-meta">
        <span class="test-lab__hero-pill">{{ currentMode }}</span>
        <span class="test-lab__hero-pill test-lab__hero-pill--muted">{{ inventoryStore.products.length }} tracked products</span>
      </div>
    </header>

    <section class="test-lab__modes surface">
      <div>
        <p class="test-lab__panel-eyebrow">Comparison mode</p>
        <h2 class="test-lab__panel-title">Choose the kind of system run you want to inspect</h2>
        <p class="test-lab__copy">{{ modeCopy }}</p>
      </div>
      <div class="test-lab__mode-switch" role="tablist" aria-label="Comparison mode">
        <button
          type="button"
          class="test-lab__mode-btn"
          :class="{ 'test-lab__mode-btn--active': compareMode === 'baseline' }"
          @click="compareMode = 'baseline'"
        >
          Baseline only
        </button>
        <button
          type="button"
          class="test-lab__mode-btn"
          :class="{ 'test-lab__mode-btn--active': compareMode === 'live' }"
          @click="compareMode = 'live'"
        >
          Live data only
        </button>
        <button
          type="button"
          class="test-lab__mode-btn"
          :class="{ 'test-lab__mode-btn--active': compareMode === 'mixed' }"
          @click="compareMode = 'mixed'"
        >
          Mixed / hybrid
        </button>
      </div>
    </section>

    <section v-if="isBaselineActive" class="test-lab__baseline surface">
      <p class="test-lab__baseline-eyebrow">Industry baseline active</p>
      <p class="test-lab__baseline-copy">
        {{ operatingAssumption || "The system is still leaning on similar-business data until this product has enough direct history." }}
      </p>
    </section>

    <div class="test-lab__grid">
      <section class="test-lab__panel surface">
        <div class="test-lab__panel-head">
          <div>
            <p class="test-lab__panel-eyebrow">Scenario builder</p>
            <h2 class="test-lab__panel-title">Edit product data and queue the events you want to test</h2>
          </div>
          <button class="btn btn-secondary btn-sm" type="button" @click="resetDraftFromProduct(selectedProduct)">
            Reset form
          </button>
        </div>

        <div class="test-lab__field-grid">
          <label class="test-lab__field">
            <span class="test-lab__label">Target product</span>
            <select v-model="selectedProductId" class="test-lab__input">
              <option value="">New sandbox product</option>
              <option v-for="product in inventoryStore.byUrgency" :key="product.id" :value="product.id">
                {{ product.name }} ({{ product.sku }})
              </option>
            </select>
          </label>

          <label class="test-lab__field">
            <span class="test-lab__label">Product name</span>
            <input v-model="productDraft.name" class="test-lab__input" type="text" placeholder="e.g. Palm oil 5L" />
          </label>

          <label class="test-lab__field">
            <span class="test-lab__label">SKU</span>
            <input v-model="productDraft.sku" class="test-lab__input" type="text" placeholder="LAB-..." />
          </label>

          <label class="test-lab__field">
            <span class="test-lab__label">Unit</span>
            <input v-model="productDraft.unit" class="test-lab__input" type="text" placeholder="units" />
          </label>

          <label class="test-lab__field">
            <span class="test-lab__label">Reorder point</span>
            <input v-model.number="productDraft.reorder_point" class="test-lab__input" type="number" min="0" step="1" />
          </label>

          <label class="test-lab__field">
            <span class="test-lab__label">Reorder quantity</span>
            <input v-model.number="productDraft.reorder_quantity" class="test-lab__input" type="number" min="0" step="1" />
          </label>

          <label class="test-lab__field test-lab__field--full">
            <span class="test-lab__label">Opening stock for scenario</span>
            <input v-model.number="productDraft.opening_stock" class="test-lab__input" type="number" min="0" step="1" />
          </label>
        </div>

        <div class="test-lab__actions">
          <button class="btn btn-secondary" type="button" :disabled="savingProduct" @click="saveProductProfile">
            {{ savingProduct ? "Saving..." : selectedProductId ? "Update product" : "Save product" }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="runningScenario || savingProduct" @click="runScenario">
            {{
              runningScenario
                ? "Running..."
                : compareMode === 'baseline'
                  ? 'Run baseline probe'
                  : compareMode === 'live'
                    ? 'Run live-data scenario'
                    : 'Run hybrid scenario'
            }}
          </button>
        </div>

        <div class="test-lab__events-head">
          <div>
            <p class="test-lab__panel-eyebrow">Event sequence</p>
            <h3 class="test-lab__section-title">Add the stock or sales events that should flow through the engine</h3>
          </div>
          <div class="test-lab__quick-adds">
            <button class="test-lab__quick" type="button" @click="addEventDraft('SALE')">Add sale</button>
            <button class="test-lab__quick" type="button" @click="addEventDraft('RESTOCK')">Add restock</button>
            <button class="test-lab__quick" type="button" @click="addEventDraft('STOCK_COUNT')">Add stock count</button>
          </div>
        </div>

        <div class="test-lab__event-list">
          <article v-for="event in scenarioEvents" :key="event.id" class="test-lab__event surface">
            <div class="test-lab__event-top">
              <div>
                <p class="test-lab__event-eyebrow">{{ event.event_type }}</p>
                <p class="test-lab__event-title">
                  {{ event.event_type === "SALE" ? "Demand pull" : event.event_type === "RESTOCK" ? "Supply push" : "Verified count" }}
                </p>
              </div>
              <button class="test-lab__remove" type="button" @click="removeEventDraft(event.id)">Remove</button>
            </div>

            <div class="test-lab__event-grid">
              <label class="test-lab__field">
                <span class="test-lab__label">Event type</span>
                <select v-model="event.event_type" class="test-lab__input">
                  <option value="SALE">Sale</option>
                  <option value="RESTOCK">Restock</option>
                  <option value="STOCK_COUNT">Stock count</option>
                </select>
              </label>

              <label v-if="event.event_type !== 'STOCK_COUNT'" class="test-lab__field">
                <span class="test-lab__label">Quantity</span>
                <input v-model.number="event.quantity" class="test-lab__input" type="number" min="0" step="1" />
              </label>

              <label v-else class="test-lab__field">
                <span class="test-lab__label">Verified quantity</span>
                <input v-model.number="event.verified_quantity" class="test-lab__input" type="number" min="0" step="1" />
              </label>

              <label class="test-lab__field">
                <span class="test-lab__label">Occurred at</span>
                <input v-model="event.occurred_at" class="test-lab__input" type="datetime-local" />
              </label>

              <label class="test-lab__field test-lab__field--full">
                <span class="test-lab__label">Notes</span>
                <input v-model="event.notes" class="test-lab__input" type="text" placeholder="Optional context for the run" />
              </label>
            </div>
          </article>
        </div>
      </section>

      <section class="test-lab__panel surface">
        <div class="test-lab__panel-head">
          <div>
            <p class="test-lab__panel-eyebrow">Live outcome</p>
            <h2 class="test-lab__panel-title">{{ currentHeadline }}</h2>
          </div>
          <NuxtLink v-if="selectedProduct?.id" :to="`/products/${selectedProduct.id}`" class="test-lab__link">
            Open product page
          </NuxtLink>
        </div>

        <div class="test-lab__stats">
          <article v-for="stat in productStats" :key="stat.label" class="test-lab__stat">
            <p class="test-lab__stat-label">{{ stat.label }}</p>
            <strong class="test-lab__stat-value">{{ stat.value }}</strong>
            <span class="test-lab__stat-hint">{{ stat.hint }}</span>
          </article>
        </div>

        <div v-if="error" class="test-lab__alert test-lab__alert--error">{{ error }}</div>
        <div v-if="statusNote" class="test-lab__alert test-lab__alert--success">{{ statusNote }}</div>

        <div v-if="selectedProduct" class="test-lab__snapshot">
          <div class="test-lab__snapshot-head">
            <div>
              <p class="test-lab__panel-eyebrow">System snapshot</p>
              <h3 class="test-lab__section-title">{{ selectedProduct.name }}</h3>
            </div>
            <span class="test-lab__tag">{{ selectedProduct.active_decision?.severity ?? "ok" }}</span>
          </div>

          <div class="test-lab__snapshot-meta">
            <span>SKU: {{ selectedProduct.sku }}</span>
            <span>Confidence: {{ Math.round(Number(selectedProduct.confidence_score ?? 0) * 100) }}%</span>
            <span>Recent events: {{ recentEvents.length }}</span>
          </div>

          <div v-if="selectedProduct.active_decision" class="test-lab__decision">
            <DecisionCard :decision="selectedProduct.active_decision" />
          </div>

          <div class="test-lab__chart-grid">
            <SalesForecastChart :burn-rate="selectedProduct.burn_rate" :recent-events="selectedProduct.recent_events" />

            <ForecastStrip
              v-if="forecastStrip.length"
              :strips="forecastStrip"
              :max-quantity="selectedProduct.estimated_quantity ?? 100"
              :current-quantity="selectedProduct.estimated_quantity"
              :recent-events="selectedProduct.recent_events"
            />
            <div v-else class="test-lab__empty surface">
              <p class="test-lab__empty-title">No forecast strip yet</p>
              <p class="test-lab__empty-copy">
                Run a stock count or a sale and the forecast strip will appear here using the live backend response.
              </p>
            </div>
          </div>

          <DecisionSimulationPanel
            v-if="decisionSimulation?.available"
            :simulation="decisionSimulation"
          />

          <div class="test-lab__recent">
            <p class="test-lab__panel-eyebrow">Recent events</p>
            <div v-if="recentEvents.length" class="test-lab__recent-list">
              <div v-for="event in recentEvents.slice(0, 5)" :key="`${event.event_type}-${event.occurred_at}`" class="test-lab__recent-item">
                <div>
                  <strong>{{ event.event_type }}</strong>
                  <p>{{ new Date(event.occurred_at).toLocaleString() }}</p>
                </div>
                <span>
                  {{
                    event.event_type === "STOCK_COUNT"
                      ? `verified ${Math.round(Number(event.verified_quantity ?? 0))}`
                      : `${Math.round(Number(event.quantity ?? 0))} units`
                  }}
                </span>
              </div>
            </div>
            <p v-else class="test-lab__empty-copy">No events yet. Save the product and run a scenario to populate this trace.</p>
          </div>
        </div>

        <div v-else class="test-lab__empty surface">
          <p class="test-lab__empty-title">Nothing selected yet</p>
          <p class="test-lab__empty-copy">
            Save the product draft or pick an existing product to see the live forecast, decision output, and simulation panel.
          </p>
        </div>
      </section>
    </div>

    <section class="test-lab__log surface">
      <div class="test-lab__panel-head">
        <div>
          <p class="test-lab__panel-eyebrow">Run log</p>
          <h2 class="test-lab__panel-title">What just happened in the system</h2>
        </div>
        <button class="btn btn-secondary btn-sm" type="button" @click="clearActivityLog">
          Clear
        </button>
      </div>

      <div v-if="activityLog.length" class="test-lab__log-list">
        <div v-for="line in activityLog" :key="line" class="test-lab__log-item">{{ line }}</div>
      </div>
      <p v-else class="test-lab__empty-copy">
        Your next save or scenario run will appear here, along with the exact path that was exercised.
      </p>
    </section>

    <div v-if="loadingCatalog" class="test-lab__loading">Loading product catalog...</div>
    <div v-else-if="syncingOutput" class="test-lab__loading">Refreshing live outputs...</div>
  </div>
</template>

<style scoped>
.test-lab {
  display: grid;
  gap: 18px;
  background:
    radial-gradient(circle at top left, rgba(83, 74, 183, 0.12), transparent 28%),
    radial-gradient(circle at top right, rgba(24, 95, 165, 0.1), transparent 24%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg) 96%, white), var(--bg));
}
.test-lab__hero,
.test-lab__baseline,
.test-lab__panel,
.test-lab__log {
  padding: 20px;
  border-radius: 24px;
}
.test-lab__hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid color-mix(in srgb, var(--purple) 12%, var(--border));
  background:
    radial-gradient(circle at top right, rgba(83, 74, 183, 0.12), transparent 38%),
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 98%, transparent), color-mix(in srgb, var(--bg-card) 92%, transparent));
}
.test-lab__eyebrow,
.test-lab__panel-eyebrow,
.test-lab__baseline-eyebrow {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-4);
}
.test-lab__title {
  margin-top: 6px;
  max-width: 16ch;
  font-size: clamp(30px, 4vw, 44px);
  line-height: 1.02;
  letter-spacing: -0.04em;
  color: var(--text);
}
.test-lab__copy,
.test-lab__baseline-copy {
  margin-top: 10px;
  max-width: 70ch;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-2);
}
.test-lab__hero-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.test-lab__hero-pill,
.test-lab__tag {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 94%, transparent);
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
}
.test-lab__hero-pill--muted {
  color: var(--text-3);
}
.test-lab__baseline {
  border: 1px solid color-mix(in srgb, #185fa5 16%, var(--border));
  background:
    linear-gradient(180deg, color-mix(in srgb, #185fa5 8%, var(--bg-card)), color-mix(in srgb, var(--bg-card) 95%, transparent));
}
.test-lab__baseline-copy {
  margin-top: 6px;
}
.test-lab__modes {
  padding: 18px 20px;
  border-radius: 24px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 96%, transparent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.test-lab__mode-switch {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.test-lab__mode-btn {
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-raised) 92%, transparent);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: transform .18s ease, border-color .18s ease, background .18s ease, color .18s ease;
}
.test-lab__mode-btn:hover {
  transform: translateY(-1px);
}
.test-lab__mode-btn--active {
  background: color-mix(in srgb, var(--purple) 12%, var(--bg-card));
  border-color: color-mix(in srgb, var(--purple) 30%, var(--border));
  color: var(--text);
}
.test-lab__grid {
  display: grid;
  grid-template-columns: minmax(340px, 0.92fr) minmax(0, 1.08fr);
  gap: 18px;
}
.test-lab__panel,
.test-lab__log {
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 96%, transparent);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.test-lab__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.test-lab__panel-title {
  margin-top: 5px;
  font-size: 18px;
  line-height: 1.24;
  color: var(--text);
}
.test-lab__section-title {
  margin-top: 4px;
  font-size: 14px;
  line-height: 1.4;
  color: var(--text);
}
.test-lab__field-grid,
.test-lab__event-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.test-lab__field,
.test-lab__event {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.test-lab__field--full {
  grid-column: 1 / -1;
}
.test-lab__label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-3);
}
.test-lab__input {
  width: 100%;
  min-height: 44px;
  padding: 0 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text);
  font-size: 14px;
}
.test-lab__input:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--purple) 42%, var(--border));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--purple) 12%, transparent);
}
.test-lab__actions,
.test-lab__quick-adds {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.test-lab__events-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.test-lab__quick,
.test-lab__remove,
.test-lab__link {
  border: 1px solid var(--border-subtle);
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-raised) 92%, transparent);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  padding: 8px 12px;
  text-decoration: none;
}
.test-lab__quick:hover,
.test-lab__remove:hover,
.test-lab__link:hover {
  color: var(--text);
  border-color: color-mix(in srgb, var(--purple) 18%, var(--border-subtle));
}
.test-lab__event-list {
  display: grid;
  gap: 12px;
}
.test-lab__event {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-raised) 88%, transparent);
}
.test-lab__event-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.test-lab__event-eyebrow {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.test-lab__event-title {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.test-lab__remove {
  padding: 7px 10px;
}
.test-lab__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.test-lab__stat {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-raised) 88%, transparent);
  display: grid;
  gap: 4px;
}
.test-lab__stat-label {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.test-lab__stat-value {
  font-size: 20px;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--text);
}
.test-lab__stat-hint,
.test-lab__empty-copy,
.test-lab__recent-item p {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-3);
}
.test-lab__alert {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 600;
}
.test-lab__alert--error {
  color: #9f1d1d;
  background: rgba(255, 77, 79, 0.08);
  border: 1px solid rgba(255, 77, 79, 0.18);
}
.test-lab__alert--success {
  color: #14532d;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.18);
}
.test-lab__snapshot {
  display: grid;
  gap: 16px;
}
.test-lab__snapshot-head,
.test-lab__recent-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.test-lab__snapshot-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-3);
}
.test-lab__decision {
  display: grid;
  gap: 12px;
}
.test-lab__chart-grid {
  display: grid;
  gap: 12px;
}
.test-lab__empty {
  padding: 18px;
  border-radius: 18px;
  border: 1px dashed var(--border);
  background: color-mix(in srgb, var(--bg-raised) 88%, transparent);
}
.test-lab__empty-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.test-lab__recent {
  display: grid;
  gap: 10px;
}
.test-lab__recent-list {
  display: grid;
  gap: 10px;
}
.test-lab__recent-item {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-raised) 88%, transparent);
}
.test-lab__recent-item strong {
  font-size: 13px;
  color: var(--text);
}
.test-lab__recent-item span {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-2);
}
.test-lab__log-list {
  display: grid;
  gap: 8px;
}
.test-lab__log-item {
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-raised) 90%, transparent);
  font-size: 12px;
  color: var(--text-2);
}
.test-lab__loading {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 94%, transparent);
  font-size: 13px;
  color: var(--text-3);
}

@media (max-width: 1080px) {
  .test-lab__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .test-lab__hero {
    flex-direction: column;
  }
  .test-lab__modes {
    flex-direction: column;
    align-items: stretch;
  }
  .test-lab__mode-switch {
    justify-content: flex-start;
  }
  .test-lab__stats,
  .test-lab__field-grid,
  .test-lab__event-grid {
    grid-template-columns: 1fr;
  }
  .test-lab__field--full {
    grid-column: auto;
  }
}
</style>
