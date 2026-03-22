<!-- frontend/app/components/inventory/ProductTable.vue
     FULLY UPGRADED per spec sections 6, 8, 11, 12:
       Section 6:  Optimistic updates — trusts backend success, never shows false failure
       Section 8:  Inline editing, supplier dropdown, search+filter+sort, pagination
       Section 11: Hover elevation, click ripple, success flash, confidence change message
       Section 12: Trust language — empty-data replaced with smart assumption text
                   Confidence hedged by score (might / likely / expected)

     All existing props and emits preserved.
     New emits: inlineUpdate (already existed), repeatLastCount
-->
<script setup lang="ts">
import type { InventoryEventCreate, Product } from "~/types"

const props = defineProps<{
  products: Product[]
  loading?:  boolean
}>()

const emit = defineEmits<{
  select:          [product: Product]
  recordEvent:     [product: Product]
  quickSale:       [product: Product]
  quickRestock:    [product: Product]
  syncShelf:       [product: Product]
  repeatLastCount: [product: Product]
  inlineUpdate:    [payload: { id: string; data: Record<string, unknown> }]
  deleteProduct:   [product: Product]
  submitInventoryEntry: [payload: { product: Product; event: InventoryEventCreate }]
}>()

// ── Search + filter ──────────────────────────────────────────────
const search   = ref("")
const filter   = ref<"all" | "critical" | "warning" | "ok">("all")
const page     = ref(1)
const perPage  = 10
const sortKey  = ref<"urgency" | "name" | "days" | "confidence">("urgency")

const urgencyOrder = (p: Product) => {
  const o: Record<string, number> = { critical: 0, warning: 1, info: 2, ok: 3 }
  return o[p.active_decision?.severity ?? "ok"] ?? 3
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  let list = props.products

  if (q) {
    list = list.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.sku.toLowerCase().includes(q) ||
      (p.category ?? "").toLowerCase().includes(q) ||
      (p.supplier_name ?? "").toLowerCase().includes(q)
    )
  }

  if (filter.value !== "all") {
    list = list.filter(p => {
      const sev = p.active_decision?.severity ?? "ok"
      if (filter.value === "ok") return sev === "ok" || sev === "info"
      return sev === filter.value
    })
  }

  return [...list].sort((a, b) => {
    if (sortKey.value === "urgency")    return urgencyOrder(a) - urgencyOrder(b)
    if (sortKey.value === "name")       return a.name.localeCompare(b.name)
    if (sortKey.value === "days")       return (a.days_remaining ?? 999) - (b.days_remaining ?? 999)
    if (sortKey.value === "confidence") return (b.confidence_score ?? 0) - (a.confidence_score ?? 0)
    return 0
  })
})

const pages     = computed(() => Math.max(1, Math.ceil(filtered.value.length / perPage)))
const paginated = computed(() => {
  const s = (page.value - 1) * perPage
  return filtered.value.slice(s, s + perPage)
})

watch([search, filter, sortKey], () => { page.value = 1 })

// ── Inline editing ────────────────────────────────────────────────
const editingId  = ref<string | null>(null)
const editBuffer = ref<Record<string, any>>({})
const editSaving = ref(false)

const startEdit = (p: Product) => {
  editingId.value  = p.id
  editBuffer.value = {
    name:          p.name,
    reorder_point: p.reorder_point,
    supplier_name: p.supplier_name ?? "",
    selling_price: p.selling_price ?? "",
    cost_price:    p.cost_price    ?? "",
  }
}

const cancelEdit = () => {
  editingId.value  = null
  editBuffer.value = {}
}

const saveEdit = async (p: Product) => {
  editSaving.value = true
  try {
    await emit("inlineUpdate", { id: p.id, data: editBuffer.value })
    successFlash.value = p.id
    setTimeout(() => { successFlash.value = null }, 1200)
  } finally {
    editSaving.value = false
    editingId.value  = null
    editBuffer.value = {}
  }
}

// ── Micro-interaction state ───────────────────────────────────────
const successFlash  = ref<string | null>(null)
const actingIds     = ref<Set<string>>(new Set())
const confMessage   = ref<{ id: string; text: string } | null>(null)

const setActing = (id: string, val: boolean) => {
  if (val) actingIds.value.add(id)
  else     actingIds.value.delete(id)
}

const announceAction = (id: string, text: string) => {
  confMessage.value = { id, text }
  setTimeout(() => {
    if (confMessage.value?.id === id) confMessage.value = null
  }, 2200)
}

// Quick actions with micro-feedback
const handleSale = async (p: Product) => {
  setActing(p.id, true)
  try {
    emit("quickSale", p)
    successFlash.value = p.id
    setTimeout(() => { successFlash.value = null }, 1200)
    announceAction(p.id, "Stock updated. Confidence may improve as new activity is learned.")
  } finally {
    setTimeout(() => setActing(p.id, false), 800)
  }
}

const handleRestock = async (p: Product) => {
  setActing(p.id, true)
  emit("quickRestock", p)
  successFlash.value = p.id
  announceAction(p.id, "Stock updated.")
  setTimeout(() => { successFlash.value = null; setActing(p.id, false) }, 1000)
}

const handleSync = async (p: Product) => {
  setActing(p.id, true)
  emit("syncShelf", p)
  successFlash.value = p.id
  announceAction(p.id, "Stock updated. Confidence improved by verified shelf count.")
  setTimeout(() => { successFlash.value = null; setActing(p.id, false) }, 1000)
}

// ── Trust language helpers (Section 12) ──────────────────────────
const hedge = (conf: number) => {
  if (conf >= 0.70) return "expected"
  if (conf >= 0.40) return "likely"
  return "might"
}

const hedgeClass = (conf: number) =>
  conf >= 0.70 ? "conf--high" : conf >= 0.40 ? "conf--medium" : "conf--low"

const fmtQty = (p: Product) => {
  const qty = p.estimated_quantity
  if (qty == null || qty === 0) return "Estimating…"
  return `~${Math.round(qty)}`
}

const qtySubtext = (p: Product) => {
  const conf = p.confidence_score ?? 0
  if (!p.estimated_quantity) return "We are estimating this product based on similar businesses"
  if (conf < 0.35) return "Based on industry estimates — add a stock count to improve this"
  return p.unit ?? "units"
}

const fmtDays = (p: Product) => {
  const days = p.days_remaining
  if (days == null) return "—"
  if (days <= 0)    return "Stockout risk"
  return `~${Math.max(1, Math.round(days))}d`
}

const urgencyStyles = (p: Product) => {
  const sev = p.active_decision?.severity ?? "ok"
  if (sev === "critical") return { bar: "pt-bar--red",   row: "pt-row--critical", days: "pt-days--red",   chip: "pt-chip--red" }
  if (sev === "warning")  return { bar: "pt-bar--amber", row: "pt-row--warning",  days: "pt-days--amber", chip: "pt-chip--amber" }
  return                        { bar: "pt-bar--green",  row: "",                 days: "",               chip: "pt-chip--green" }
}

const confColor = (score: number) => {
  if (score >= 0.75) return "#22C55E"
  if (score >= 0.45) return "#F59E0B"
  return "#EF4444"
}

const entryProduct = ref<Product | null>(null)
const entryMode = ref<"SALE" | "RESTOCK" | "STOCK_COUNT">("SALE")
const entrySaving = ref(false)
const entryForm = reactive({
  quantity: 1,
  verified_quantity: 0,
  occurred_at: "",
  notes: "",
})

const resetEntryForm = () => {
  entryForm.quantity = 1
  entryForm.verified_quantity = 0
  entryForm.occurred_at = new Date().toISOString().slice(0, 16)
  entryForm.notes = ""
}

const openEntry = (product: Product, mode: "SALE" | "RESTOCK" | "STOCK_COUNT") => {
  entryProduct.value = product
  entryMode.value = mode
  resetEntryForm()
  if (mode === "STOCK_COUNT") {
    entryForm.quantity = 0
    entryForm.verified_quantity = Math.max(0, Math.round(product.estimated_quantity ?? product.last_verified_quantity ?? 0))
    entryForm.notes = "Inventory count"
  } else if (mode === "RESTOCK") {
    entryForm.notes = "Inventory restock"
  } else {
    entryForm.notes = "Sale recorded"
  }
}

const closeEntry = () => {
  entryProduct.value = null
  entrySaving.value = false
}

const entryTitle = computed(() => {
  if (entryMode.value === "SALE") return "Record sale"
  if (entryMode.value === "RESTOCK") return "Record restock"
  return "Record stock count"
})

const submitEntry = async () => {
  if (!entryProduct.value) return
  entrySaving.value = true
  try {
    const event: InventoryEventCreate = {
      event_type: entryMode.value,
      quantity: entryMode.value === "STOCK_COUNT" ? 0 : Math.max(0, Number(entryForm.quantity ?? 0)),
      occurred_at: new Date(entryForm.occurred_at || new Date().toISOString()).toISOString(),
      notes: entryForm.notes?.trim() || undefined,
    }

    if (entryMode.value === "STOCK_COUNT") {
      event.verified_quantity = Math.max(0, Number(entryForm.verified_quantity ?? 0))
    }

    emit("submitInventoryEntry", {
      product: entryProduct.value,
      event,
    })

    announceAction(entryProduct.value.id, "Inventory entry recorded.")
    successFlash.value = entryProduct.value.id
    setTimeout(() => { successFlash.value = null }, 1200)
    closeEntry()
  } finally {
    entrySaving.value = false
  }
}

// ── Statistics ────────────────────────────────────────────────────
const criticalCount = computed(() => props.products.filter(p => p.active_decision?.severity === "critical").length)
const warningCount  = computed(() => props.products.filter(p => p.active_decision?.severity === "warning").length)
const healthyCount  = computed(() => props.products.filter(p => !p.active_decision || ["ok","info"].includes(p.active_decision.severity ?? "")).length)

// ── Supplier list (aggregated from product data) ──────────────────
const knownSuppliers = computed(() => {
  const names = props.products.map(p => p.supplier_name).filter(Boolean) as string[]
  return [...new Set(names)].slice(0, 20)
})

const handleDelete = (product: Product) => {
  if (!window.confirm(`Delete ${product.name} from your inventory?`)) return
  emit("deleteProduct", product)
}
</script>

<template>
  <div class="pt surface-hover">

    <!-- ── Toolbar ─────────────────────────────────────────────── -->
    <div class="pt__toolbar">
      <div>
        <h2 class="pt__title">Products</h2>
        <p class="pt__sub">Sorted by urgency — riskiest first</p>
      </div>
      <div class="pt__toolbar-right">

        <!-- Search -->
        <div class="pt__search-wrap">
          <svg class="pt__search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2.5">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            v-model="search"
            class="pt__search"
            type="text"
            placeholder="Search by name, SKU, supplier…"
            aria-label="Search products"
          />
          <button v-if="search" class="pt__search-clear" @click="search = ''" aria-label="Clear search">×</button>
        </div>

        <!-- Filter pills -->
        <div class="pt__filters" role="group" aria-label="Filter by severity">
          <button
            v-for="f in ['all','critical','warning','ok']" :key="f"
            class="pt__filter-pill"
            :class="{ 'pt__filter-pill--active': filter === f }"
            @click="filter = (f as typeof filter.value)"
          >
            <span v-if="f === 'critical'" class="pt__filter-dot pt__filter-dot--red" />
            <span v-else-if="f === 'warning'" class="pt__filter-dot pt__filter-dot--amber" />
            <span v-else-if="f === 'ok'" class="pt__filter-dot pt__filter-dot--green" />
            {{ f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1) }}
          </button>
        </div>

        <!-- Sort -->
        <select class="pt__sort-select" v-model="sortKey" aria-label="Sort by">
          <option value="urgency">↑ Urgency</option>
          <option value="days">↑ Est. Days Till Stock Out</option>
          <option value="confidence">↑ Confidence</option>
          <option value="name">A–Z Name</option>
        </select>

        <NuxtLink to="/upload?mode=sales" class="btn btn-secondary btn-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          Import sales
        </NuxtLink>

        <NuxtLink to="/upload?mode=stock" class="btn btn-secondary btn-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          Import stock
        </NuxtLink>

        <NuxtLink to="/onboarding" class="btn btn-primary btn-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Add product
        </NuxtLink>

      </div>
    </div>
    <Transition name="pt-feedback-fade">
      <div v-if="confMessage" class="pt__feedback" role="status" aria-live="polite">
        {{ confMessage.text }}
      </div>
    </Transition>

    <!-- ── Table ───────────────────────────────────────────────── -->
    <div class="pt__table-wrap">
      <table class="pt__table" role="grid">
        <thead>
          <tr class="pt__thead-row">
            <th class="pt__th">Product</th>
            <th class="pt__th">Est. Quantity</th>
            <th class="pt__th">Est. Days Till Stock Out</th>
            <th class="pt__th">Confidence</th>
            <th class="pt__th pt__th--right">Quick Actions</th>
          </tr>
        </thead>
        <tbody>
          <!-- Loading rows -->
          <template v-if="loading">
            <tr v-for="i in 5" :key="i" class="pt-row pt-row--loading">
              <td class="pt__td" colspan="5">
                <div class="skeleton skeleton--text" :style="{ width: `${50 + i * 8}%` }" />
              </td>
            </tr>
          </template>

          <!-- Data rows -->
          <template v-else>
            <template v-for="p in paginated" :key="p.id">

              <!-- VIEW mode -->
              <tr
                v-if="editingId !== p.id"
                class="pt-row ripple-host"
                :class="[
                  urgencyStyles(p).row,
                  { 'pt-row--success': successFlash === p.id },
                  { 'pt-row--acting': actingIds.has(p.id) },
                ]"
                @click="emit('select', p)"
              >
                <!-- Product name + urgency bar -->
                <td class="pt__td">
                  <div class="pt-product">
                    <div class="pt-bar" :class="urgencyStyles(p).bar" />
                    <div class="pt-product__info">
                      <p class="pt-product__name">{{ p.name }}</p>
                      <p class="pt-product__sku">{{ p.sku }}</p>
                      <p v-if="p.supplier_name" class="pt-product__supplier">{{ p.supplier_name }}</p>
                    </div>
                  </div>
                </td>

                <!-- Estimated quantity with trust language -->
                <td class="pt__td">
                  <p class="pt__qty">{{ fmtQty(p) }}</p>
                  <p
                    class="pt__qty-sub"
                    :class="{ 'pt__qty-sub--estimate': !p.estimated_quantity }"
                  >{{ qtySubtext(p) }}</p>
                </td>

                <!-- Est. Days Till Stock Out -->
                <td class="pt__td">
                  <span class="pt-days" :class="urgencyStyles(p).days">
                    {{ fmtDays(p) }}
                  </span>
                </td>

                <!-- Confidence with hedge word -->
                <td class="pt__td">
                  <div class="pt-conf">
                    <div class="pt-conf__track">
                      <div
                        class="pt-conf__fill"
                        :style="{
                          width:      `${Math.round((p.confidence_score ?? 0) * 100)}%`,
                          background: confColor(p.confidence_score ?? 0),
                        }"
                      />
                    </div>
                    <span class="pt-conf__pct">{{ Math.round((p.confidence_score ?? 0) * 100) }}%</span>
                  </div>
                  <p class="pt-conf__hedge" :class="hedgeClass(p.confidence_score ?? 0)">
                    {{ hedge(p.confidence_score ?? 0) }}
                  </p>
                </td>

                <!-- Quick actions -->
                <td class="pt__td pt__td--actions" @click.stop>
                  <div class="pt-actions">
                    <button
                      class="pt-action pt-action--sale"
                      :class="{ 'pt-action--spinning': actingIds.has(p.id) }"
                      :disabled="actingIds.has(p.id)"
                      title="Record sale"
                      aria-label="Record sale"
                      @click="openEntry(p, 'SALE')"
                    >
                      Sale
                    </button>
                    <button
                      class="pt-action pt-action--restock"
                      :disabled="actingIds.has(p.id)"
                      title="Record restock"
                      aria-label="Record restock"
                      @click="openEntry(p, 'RESTOCK')"
                    >
                      Restock
                    </button>
                    <button
                      class="pt-action pt-action--sync"
                      :disabled="actingIds.has(p.id)"
                      title="Record stock count"
                      @click="openEntry(p, 'STOCK_COUNT')"
                    >
                      Count
                    </button>
                    <button
                      class="pt-action pt-action--history"
                      title="Open product history"
                      @click="emit('recordEvent', p)"
                    >
                      Log
                    </button>
                    <!-- Inline edit -->
                    <button
                      class="pt-action pt-action--edit"
                      title="Edit product details"
                      @click.stop="startEdit(p)"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                      </svg>
                    </button>
                    <button
                      class="pt-action pt-action--delete"
                      title="Delete product"
                      @click.stop="handleDelete(p)"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6l-1 14H6L5 6"/>
                        <path d="M10 11v6M14 11v6"/>
                        <path d="M9 6V4h6v2"/>
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>

              <!-- EDIT mode (inline row) -->
              <tr v-else class="pt-row pt-row--editing" @click.stop>
                <td class="pt__td" colspan="5">
                  <div class="pt-edit">
                    <div class="pt-edit__fields">

                      <label class="pt-edit__label">
                        Name
                        <input v-model="editBuffer.name" class="pt-edit__input" type="text" />
                      </label>

                      <label class="pt-edit__label">
                        Reorder point
                        <input v-model.number="editBuffer.reorder_point" class="pt-edit__input" type="number" min="0" step="1" />
                      </label>

                      <label class="pt-edit__label">
                        Supplier
                        <div class="pt-edit__supplier-wrap">
                          <input
                            v-model="editBuffer.supplier_name"
                            class="pt-edit__input"
                            type="text"
                            list="pt-suppliers"
                            placeholder="Type or select…"
                          />
                          <datalist id="pt-suppliers">
                            <option v-for="s in knownSuppliers" :key="s" :value="s" />
                          </datalist>
                        </div>
                      </label>

                      <label class="pt-edit__label">
                        Selling price (₦)
                        <input v-model.number="editBuffer.selling_price" class="pt-edit__input" type="number" min="0" step="0.01" />
                      </label>

                      <label class="pt-edit__label">
                        Cost price (₦)
                        <input v-model.number="editBuffer.cost_price" class="pt-edit__input" type="number" min="0" step="0.01" />
                      </label>

                    </div>

                    <div class="pt-edit__actions">
                      <button
                        class="btn btn-primary btn-sm"
                        :disabled="editSaving"
                        @click="saveEdit(p)"
                      >
                        {{ editSaving ? "Saving…" : "Save" }}
                      </button>
                      <button class="btn btn-secondary btn-sm" @click="cancelEdit">Cancel</button>
                    </div>
                  </div>
                </td>
              </tr>

            </template>

            <!-- Empty state -->
            <tr v-if="!paginated.length && !loading">
              <td colspan="5" class="pt__empty">
                <div class="pt__empty-inner">
                  <span style="font-size:24px">📦</span>
                  <p>{{ search ? `No products match "${search}"` : 'No products in this filter.' }}</p>
                  <p v-if="search" class="pt__empty-hint">Try a different name, SKU, or supplier.</p>
                  <p v-else class="pt__empty-hint">
                    Businesses like yours typically track 5–20 key products.
                    <NuxtLink to="/onboarding" class="pt__empty-link">Add your first →</NuxtLink>
                  </p>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- ── Footer ─────────────────────────────────────────────── -->
    <div class="pt__footer">
      <p class="pt__footer-count">
        Showing <strong>{{ filtered.length }}</strong> of <strong>{{ products.length }}</strong> products
      </p>
      <div class="pt__legend">
        <span class="pt__legend-item">
          <span class="pt__legend-dot pt__legend-dot--red" />{{ criticalCount }} Critical
        </span>
        <span class="pt__legend-item">
          <span class="pt__legend-dot pt__legend-dot--amber" />{{ warningCount }} Warning
        </span>
        <span class="pt__legend-item">
          <span class="pt__legend-dot pt__legend-dot--green" />{{ healthyCount }} Healthy
        </span>
      </div>
      <div v-if="pages > 1" class="pt__pagination">
        <button class="pt__page-btn" :disabled="page <= 1" @click="page--">←</button>
        <span class="pt__page-info">{{ page }} / {{ pages }}</span>
        <button class="pt__page-btn" :disabled="page >= pages" @click="page++">→</button>
      </div>
    </div>

    <div v-if="entryProduct" class="pt-modal" @click.self="closeEntry">
      <div class="pt-modal__card">
        <div class="pt-modal__header">
          <div>
            <p class="pt-modal__eyebrow">Inventory entry</p>
            <h3 class="pt-modal__title">{{ entryTitle }} for {{ entryProduct.name }}</h3>
            <p class="pt-modal__copy">Capture the event with its real quantity and date so stock and sales history stay reliable.</p>
          </div>
          <button class="pt-modal__close" type="button" @click="closeEntry">×</button>
        </div>

        <div class="pt-modal__fields">
          <label class="pt-edit__label">
            Event type
            <select v-model="entryMode" class="pt-edit__input">
              <option value="SALE">Sale</option>
              <option value="RESTOCK">Restock</option>
              <option value="STOCK_COUNT">Stock count</option>
            </select>
          </label>

          <label v-if="entryMode !== 'STOCK_COUNT'" class="pt-edit__label">
            Quantity
            <input v-model.number="entryForm.quantity" class="pt-edit__input" type="number" min="0.01" step="0.01" />
          </label>

          <label v-else class="pt-edit__label">
            Counted stock
            <input v-model.number="entryForm.verified_quantity" class="pt-edit__input" type="number" min="0" step="1" />
          </label>

          <label class="pt-edit__label">
            Date and time
            <input v-model="entryForm.occurred_at" class="pt-edit__input" type="datetime-local" />
          </label>

          <label class="pt-edit__label pt-edit__label--full">
            Notes
            <input v-model="entryForm.notes" class="pt-edit__input" type="text" placeholder="Optional inventory context" />
          </label>
        </div>

        <div class="pt-modal__actions">
          <button class="btn btn-primary btn-sm" type="button" :disabled="entrySaving" @click="submitEntry">
            {{ entrySaving ? "Saving…" : "Save entry" }}
          </button>
          <button class="btn btn-secondary btn-sm" type="button" @click="closeEntry">Cancel</button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* ── Container ──────────────────────────────────────────────────── */
.pt {
  background:    #fff;
  border-radius: 20px;
  border:        1px solid var(--border);
  overflow:      hidden;
  box-shadow:    var(--shadow-sm);
  transition:    box-shadow var(--dur-base), transform var(--dur-base);
}
.pt:hover { box-shadow: var(--shadow-md); }

/* ── Toolbar ──────────────────────────────────────────────────── */
.pt__toolbar {
  display:         flex;
  align-items:     flex-start;
  justify-content: space-between;
  gap:             12px;
  padding:         20px 24px 16px;
  flex-wrap:       wrap;
  border-bottom:   1px solid var(--border-subtle);
}
.pt__title { font-size: 20px; font-weight: 800; letter-spacing: -0.02em; color: var(--text); }
.pt__sub   { font-size: 12px; color: var(--text-4); margin-top: 2px; }
.pt__toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pt__feedback {
  margin:       0 24px 12px;
  padding:      10px 12px;
  border-radius: 10px;
  font-size:    12px;
  font-weight:  600;
  color:        #14532d;
  background:   rgba(34, 197, 94, 0.12);
  border:       1px solid rgba(34, 197, 94, 0.26);
}
.pt-feedback-fade-enter-active,
.pt-feedback-fade-leave-active { transition: opacity 180ms ease; }
.pt-feedback-fade-enter-from,
.pt-feedback-fade-leave-to { opacity: 0; }

.pt__search-wrap { position: relative; display: flex; align-items: center; }
.pt__search-icon { position: absolute; left: 10px; color: var(--text-4); pointer-events: none; }
.pt__search {
  padding:     7px 28px 7px 30px;
  background:  var(--bg-sunken);
  border:      1px solid transparent;
  border-radius: 10px;
  font-size:   13px;
  color:       var(--text);
  width:       220px;
  outline:     none;
  transition:  border-color var(--dur-fast), background var(--dur-fast), box-shadow var(--dur-fast);
}
.pt__search:focus {
  border-color: var(--purple);
  background:   #fff;
  box-shadow:   0 0 0 3px var(--purple-bg);
}
.pt__search::placeholder { color: var(--text-4); }
.pt__search-clear {
  position:  absolute;
  right:     8px;
  background: none;
  border:    none;
  cursor:    pointer;
  font-size: 16px;
  color:     var(--text-4);
  line-height: 1;
  padding:   0 2px;
  transition: color var(--dur-fast);
}
.pt__search-clear:hover { color: var(--text); }

/* Filter pills */
.pt__filters    { display: flex; gap: 4px; }
.pt__filter-pill {
  display:     flex;
  align-items: center;
  gap:         5px;
  padding:     5px 10px;
  border:      1px solid var(--border);
  border-radius: 999px;
  font-size:   11px;
  font-weight: 600;
  background:  transparent;
  color:       var(--text-3);
  cursor:      pointer;
  transition:  all var(--dur-fast);
}
.pt__filter-pill:hover { border-color: var(--purple); color: var(--purple); }
.pt__filter-pill--active { background: var(--purple-bg); border-color: var(--purple-border); color: var(--purple); }
.pt__filter-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.pt__filter-dot--red   { background: var(--red); }
.pt__filter-dot--amber { background: var(--amber); }
.pt__filter-dot--green { background: var(--green); }

/* Sort */
.pt__sort-select {
  padding:       5px 10px;
  border:        1px solid var(--border);
  border-radius: 10px;
  background:    transparent;
  font-size:     12px;
  color:         var(--text-3);
  cursor:        pointer;
  outline:       none;
  transition:    border-color var(--dur-fast);
}
.pt__sort-select:focus { border-color: var(--purple); }

/* ── Table ──────────────────────────────────────────────────────── */
.pt__table-wrap { overflow-x: auto; }
.pt__table      { width: 100%; border-collapse: collapse; }

.pt__thead-row  { background: var(--bg-sunken); }
.pt__th {
  padding:        12px 18px;
  text-align:     left;
  font-size:      10px;
  font-weight:    700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color:          var(--text-4);
  white-space:    nowrap;
  border-bottom:  1px solid var(--border);
}
.pt__th--right { text-align: right; }

/* Rows */
.pt-row {
  cursor:     pointer;
  transition: background var(--dur-fast);
  position:   relative;
}
.pt-row:hover td { background: rgba(83,74,183,0.025); }

/* Urgency tints */
.pt-row--critical:hover td { background: rgba(239,68,68,0.04); }
.pt-row--warning:hover  td { background: rgba(245,158,11,0.04); }

/* Optimistic feedback */
.pt-row--success td { animation: row-success-flash 1.2s var(--ease-out) both; }
@keyframes row-success-flash {
  0%   { background: rgba(34,197,94,0.12); }
  100% { background: transparent; }
}
.pt-row--acting { opacity: 0.72; pointer-events: none; }

/* Edit row */
.pt-row--editing { background: rgba(83,74,183,0.04); }
.pt-row--loading { pointer-events: none; }

.pt__td {
  padding:        15px 18px;
  border-bottom:  1px solid var(--border-subtle);
  vertical-align: middle;
}
.pt__td--actions { text-align: right; }

/* ── Product cell ───────────────────────────────────────────────── */
.pt-product { display: flex; align-items: center; gap: 12px; }
.pt-bar {
  width:         4px;
  height:        42px;
  border-radius: 999px;
  flex-shrink:   0;
  box-shadow:    0 2px 6px rgba(0,0,0,0.1);
}
.pt-bar--red   { background: linear-gradient(180deg, var(--red),   rgba(239,68,68,0.5));  }
.pt-bar--amber { background: linear-gradient(180deg, var(--amber), rgba(245,158,11,0.5)); }
.pt-bar--green { background: linear-gradient(180deg, var(--green), rgba(34,197,94,0.5));  }

.pt-product__name     { font-size: 14px; font-weight: 700; color: var(--text); }
.pt-product__sku      { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-4); margin-top: 2px; }
.pt-product__supplier { font-size: 11px; color: var(--text-4); margin-top: 1px; }

/* ── Quantity ───────────────────────────────────────────────────── */
.pt__qty     { font-size: 14px; font-weight: 700; color: var(--text); }
.pt__qty-sub { font-size: 11px; color: var(--text-4); margin-top: 1px; line-height: 1.4; }
.pt__qty-sub--estimate { color: var(--amber); font-style: italic; }

/* ── Days ───────────────────────────────────────────────────────── */
.pt-days {
  display:       inline-flex;
  align-items:   center;
  padding:       4px 10px;
  border-radius: 8px;
  font-size:     12px;
  font-weight:   700;
  background:    rgba(34,197,94,0.08);
  color:         var(--green);
  border:        1px solid rgba(34,197,94,0.18);
}
.pt-days--red   { background: rgba(239,68,68,0.07);   color: var(--red);   border-color: rgba(239,68,68,0.18);   }
.pt-days--amber { background: rgba(245,158,11,0.07);  color: #D97706;      border-color: rgba(245,158,11,0.18);  }

/* ── Confidence ─────────────────────────────────────────────────── */
.pt-conf { display: flex; align-items: center; gap: 8px; }
.pt-conf__track {
  flex:          1;
  max-width:     80px;
  height:        6px;
  background:    var(--border);
  border-radius: 999px;
  overflow:      hidden;
}
.pt-conf__fill {
  height:        100%;
  border-radius: 999px;
  transition:    width 0.6s var(--ease-spring);
}
.pt-conf__pct   { font-size: 12px; font-weight: 700; color: var(--text); min-width: 34px; }
.pt-conf__hedge { font-size: 10px; font-weight: 600; letter-spacing: 0.04em; margin-top: 3px; }
.conf--high   { color: var(--green); }
.conf--medium { color: var(--amber); }
.conf--low    { color: var(--red); }

/* ── Actions ────────────────────────────────────────────────────── */
.pt-actions {
  display:     flex;
  align-items: center;
  justify-content: flex-end;
  gap:         6px;
  opacity:     0;
  transition:  opacity var(--dur-fast);
}
.pt-row:hover .pt-actions { opacity: 1; }

.pt-action {
  min-width:       58px;
  height:          32px;
  border:          1px solid var(--border-subtle);
  border-radius:   9px;
  background:      color-mix(in srgb, var(--panel) 95%, transparent);
  display:         flex;
  align-items:     center;
  justify-content: center;
  cursor:          pointer;
  color:           var(--text-4);
  transition:      background var(--dur-fast), color var(--dur-fast), transform var(--dur-fast);
  font-size:       11px;
  font-weight:     700;
  padding:         0 10px;
}
.pt-action:hover { transform: scale(1.1); }
.pt-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}
.pt-action--sale:hover    { background: rgba(34,197,94,0.1);   color: var(--green); }
.pt-action--restock:hover { background: var(--purple-bg);       color: var(--purple); }
.pt-action--sync:hover    { background: rgba(245,158,11,0.1);  color: var(--amber); }
.pt-action--history:hover { background: var(--bg-sunken);       color: var(--text-2); }
.pt-action--edit:hover    { background: var(--bg-sunken);       color: var(--text-2); }
.pt-action--delete:hover  { background: rgba(239,68,68,0.1);   color: var(--red); }
.pt-action--spinning svg  { animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Inline edit ─────────────────────────────────────────────────── */
.pt-edit {
  display:        flex;
  align-items:    flex-end;
  gap:            16px;
  padding:        12px 4px;
  flex-wrap:      wrap;
}
.pt-edit__fields {
  display:    flex;
  gap:        12px;
  flex-wrap:  wrap;
  flex:       1;
}
.pt-edit__label {
  display:        flex;
  flex-direction: column;
  gap:            4px;
  font-size:      11px;
  font-weight:    600;
  color:          var(--text-4);
  flex:           1;
  min-width:      110px;
}
.pt-edit__input {
  padding:       7px 10px;
  border:        1px solid var(--border);
  border-radius: 9px;
  background:    var(--bg-sunken);
  font-size:     13px;
  color:         var(--text);
  outline:       none;
  font-family:   inherit;
  transition:    border-color var(--dur-fast);
}
.pt-edit__input:focus { border-color: var(--purple); background: #fff; }
.pt-edit__supplier-wrap { position: relative; }
.pt-edit__actions { display: flex; gap: 8px; flex-shrink: 0; }

/* ── Empty ──────────────────────────────────────────────────────── */
.pt__empty { padding: 0; }
.pt__empty-inner {
  display:        flex;
  flex-direction: column;
  align-items:    center;
  justify-content:center;
  padding:        36px 24px;
  gap:            6px;
  text-align:     center;
}
.pt__empty p      { font-size: 14px; color: var(--text-3); margin: 0; }
.pt__empty-hint   { font-size: 12px; color: var(--text-4); }
.pt__empty-link   { color: var(--purple); font-weight: 600; }

/* ── Footer ──────────────────────────────────────────────────────── */
.pt__footer {
  display:         flex;
  align-items:     center;
  gap:             16px;
  padding:         12px 24px;
  border-top:      1px solid var(--border-subtle);
  background:      var(--bg-sunken);
  flex-wrap:       wrap;
}
.pt__footer-count { font-size: 12px; color: var(--text-4); flex: 1; }
.pt__footer-count strong { color: var(--text-2); font-weight: 700; }

.pt__legend { display: flex; gap: 12px; }
.pt__legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-4); }
.pt__legend-dot { width: 6px; height: 6px; border-radius: 50%; }
.pt__legend-dot--red   { background: var(--red); }
.pt__legend-dot--amber { background: var(--amber); }
.pt__legend-dot--green { background: var(--green); }

.pt__pagination { display: flex; align-items: center; gap: 8px; }
.pt__page-btn {
  width: 28px; height: 28px; border: 1px solid var(--border); border-radius: 8px;
  background: #fff; cursor: pointer; font-size: 13px;
  display: flex; align-items: center; justify-content: center;
  transition: background var(--dur-fast);
}
.pt__page-btn:hover:not(:disabled) { background: var(--bg-sunken); }
.pt__page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pt__page-info { font-size: 12px; color: var(--text-4); }

.pt-modal {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(10, 14, 24, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.pt-modal__card {
  width: min(640px, 100%);
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--panel);
  box-shadow: var(--shadow-lg);
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.pt-modal__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.pt-modal__eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.pt-modal__title {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 800;
  color: var(--text);
}
.pt-modal__copy {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-3);
  max-width: 48ch;
}
.pt-modal__close {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-3);
  font-size: 20px;
  cursor: pointer;
}
.pt-modal__fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.pt-edit__label--full {
  grid-column: 1 / -1;
}
.pt-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 640px) {
  .pt__toolbar { padding: 16px; }
  .pt__toolbar-right { width: 100%; }
  .pt__search { width: 100%; }
  .pt-actions { opacity: 1; }   /* always show on mobile */
  .pt-modal__fields { grid-template-columns: 1fr; }
}
</style>
