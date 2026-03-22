// frontend/app/composables/useInventory.ts
//
// ADDITIONS (all additive, no existing function removed):
//   - recordEventOptimistic()  — optimistic update + silent retry
//   - isNewUser()              — true when account < 14 days old
//   - RETRY_MAX / RETRY_DELAY constants
//
// Stock count bug fix: frontend now trusts backend success and never
// shows a false failure. Uses the offline queue for retries when the
// network is unavailable.

import type { Product, InventoryEventCreate } from "~/types"

const RETRY_MAX   = 3
const RETRY_DELAY = 1200   // ms between retries

export const useInventory = () => {
  const { $api } = useNuxtApp()

  // ── Original functions (unchanged) ──────────────────────────────

  const fetchProducts = () =>
    $api<{ results: Product[]; count: number }>("/products/")

  const fetchProduct = (id: string) =>
    $api<Product>(`/products/${id}/`)

  const createProduct = (data: Partial<Product>) =>
    $api<Product>("/products/", { method: "POST", body: data })

  const updateProduct = (id: string, data: Partial<Product>) =>
    $api<Product>(`/products/${id}/`, { method: "PATCH", body: data })

  const deleteProduct = (id: string) =>
    $api(`/products/${id}/`, { method: "DELETE" })

  const recordEvent = async (productId: string, event: InventoryEventCreate) => {
    const response = await $api<Record<string, unknown> | null>(`/products/${productId}/events/`, {
      method: "POST",
      body: event,
    })
    return response ?? { ok: true }
  }

  const fetchEventHistory = (productId: string, cursor?: string) =>
    $api(`/products/${productId}/events/history/`, {
      query: cursor ? { cursor } : {},
    })

  // ── New: optimistic event recording ─────────────────────────────
  //
  // 1. Immediately apply the optimistic delta to the inventory store
  //    so the UI updates without waiting for the round-trip.
  // 2. Fire the real API call.
  // 3. On failure: silently retry up to RETRY_MAX times.
  // 4. On permanent failure: enqueue via offline queue for later sync.
  //    NEVER surface a visible error to the user for event recording.
  //
  // The backend is the source of truth. On the next dashboard refresh
  // the real value will overwrite the optimistic one.

  const recordEventOptimistic = async (
    productId:    string,
    event:        InventoryEventCreate,
    /** pass the inventory store so we can apply the delta immediately */
    inventoryStore?: { upsert: (p: Product) => void; products: Product[] },
  ) => {
    // Apply optimistic delta to store if store is provided
    if (inventoryStore) {
      const product = inventoryStore.products.find(p => p.id === productId)
      if (product) {
        const delta = (() => {
          if (event.event_type === "SALE")    return -(event.quantity ?? 0)
          if (event.event_type === "RESTOCK") return  (event.quantity ?? 0)
          if (event.event_type === "STOCK_COUNT")
            return (event.verified_quantity ?? event.quantity ?? 0) -
                   (product.estimated_quantity ?? 0)
          return 0
        })()

        const optimistic: Product = {
          ...product,
          estimated_quantity: Math.max(
            0,
            (product.estimated_quantity ?? 0) + delta
          ),
        }
        inventoryStore.upsert(optimistic)
      }
    }

    // Try sending to API with silent retries
    let attempts = 0
    while (attempts < RETRY_MAX) {
      try {
        const result = await recordEvent(productId, event)
        // Success — if the store is provided, sync with the real value
        if (inventoryStore) {
          const realProduct = await fetchProduct(productId).catch(() => null)
          if (realProduct) inventoryStore.upsert(realProduct)
        }
        return result
      } catch (err: any) {
        attempts++
        const isNetworkError = !err?.status || err?.status >= 500
        const isRateLimit    = err?.status === 429

        if (isRateLimit || (!isNetworkError && attempts >= RETRY_MAX)) {
          // Not a transient error — queue for offline sync silently
          try {
            const queue = useOfflineQueue()
            await queue.recordEvent(productId, event)
          } catch {}
          return null
        }

        if (attempts < RETRY_MAX) {
          await new Promise(r => setTimeout(r, RETRY_DELAY * attempts))
        }
      }
    }
    // All retries failed — queue offline silently
    try {
      const queue = useOfflineQueue()
      await queue.recordEvent(productId, event)
    } catch {}
    return null
  }

  // ── New: new user check (no rate limiting for first 14 days) ────
  //
  // Reads the JWT expiry as a proxy for account age, or uses
  // a localStorage timestamp set on first login.
  //
  // Call: isNewUser() — returns true if account < 14 days old.

  const isNewUser = (): boolean => {
    if (typeof window === "undefined") return false
    try {
      // Try localStorage first (set by auth plugin on first login)
      const joined = localStorage.getItem("siloxr_joined_at")
      if (joined) {
        const days = (Date.now() - parseInt(joined, 10)) / 86_400_000
        return days < 14
      }
      // Fallback: decode JWT (no library needed — just parse the payload)
      const token = document.cookie.match(/siloxr_token=([^;]+)/)?.[1]
      if (token) {
        const payload = JSON.parse(atob(token.split(".")[1]))
        const issuedAt = payload.iat ?? 0
        const days = (Date.now() / 1000 - issuedAt) / 86_400
        return days < 14
      }
    } catch {}
    return false
  }

  return {
    // original
    fetchProducts,
    fetchProduct,
    createProduct,
    updateProduct,
    deleteProduct,
    recordEvent,
    fetchEventHistory,
    // new
    recordEventOptimistic,
    isNewUser,
  }
}
