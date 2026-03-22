// frontend/app/stores/inventory.ts

import { defineStore } from "pinia"
import type { Product } from "~/types"

export const useInventoryStore = defineStore("inventory", () => {
  const products  = ref<Product[]>([])
  const selected  = ref<Product | null>(null)
  const loading   = ref(false)
  const total     = ref(0)

  const { fetchProducts, fetchProduct } = useInventory()

  const load = async () => {
    loading.value = true
    try {
      const res   = await fetchProducts()
      products.value = res.results
      total.value    = res.count
    } finally {
      loading.value = false
    }
  }

  const select = async (id: string) => {
    selected.value = await fetchProduct(id)
  }

  const upsert = (product: Product) => {
    const idx = products.value.findIndex(p => p.id === product.id)
    if (idx >= 0) products.value[idx] = product
    else products.value.unshift(product)
  }

  const remove = (id: string) => {
    products.value = products.value.filter(p => p.id !== id)
  }

  // Derived: products sorted by decision severity
  const byUrgency = computed(() => {
    const order: Record<string, number> = {
      critical: 0, warning: 1, info: 2, ok: 3,
    }
    return [...products.value].sort((a, b) => {
      const sa = order[a.active_decision?.severity ?? "ok"] ?? 3
      const sb = order[b.active_decision?.severity ?? "ok"] ?? 3
      return sa - sb
    })
  })

  return { products, selected, loading, total, load, select, upsert, remove, byUrgency }
})