// frontend/app/composables/useOfflineQueue.ts

import { useOfflineStore } from "~/stores/offline"

export const useOfflineQueue = () => {
  const store    = useOfflineStore()
  const { $api } = useNuxtApp()
  const isOnline = useOnline()

  const recordEvent = async (
    productId: string,
    event: Record<string, unknown>
  ) => {
    if (!productId || productId === "undefined") {
      console.error("recordEvent called with invalid productId:", productId)
      throw new Error("Product ID is required to record an event.")
    }

    const clientEventId = crypto.randomUUID()

    const payload = {
      ...event,
      product_id:       productId,
      client_event_id:  clientEventId,
      is_offline_event: !isOnline.value,
      occurred_at:      event.occurred_at ?? new Date().toISOString(),
    }

    if (!isOnline.value) {
      store.enqueue(payload)
      return { queued: true, clientEventId }
    }

    try {
      const result = await $api(`/products/${productId}/events/`, {
        method: "POST",
        body: payload,
      })
      return { queued: false, result }
    } catch (e: any) {
      console.error("API ERROR:", e)
      console.error("RESPONSE:", e?.response?._data || e?.data)

      store.enqueue(payload)
      return { queued: true, clientEventId }
    }
  }

  const sync = async () => {
    const queue = store.queue
    if (queue.length === 0) return

    store.setSyncing(true)

    try {
      const response = await $api<{
        summary: { succeeded: number; skipped: number; failed: number }
        results: Array<{ client_event_id: string; status: string }>
      }>("/events/sync/bulk/", {
        method: "POST",
        body: { events: queue },
      })

      const synced = response.results
        .filter(r => r.status === "created" || r.status === "duplicate")
        .map(r => r.client_event_id)

      store.clearSynced(synced)
      return response.summary
    } catch (e) {
      console.error("Sync failed:", e)
    } finally {
      store.setSyncing(false)
    }
  }

  watch(isOnline, (online) => {
    if (online && store.queue.length > 0) {
      sync()
    }
  })

  return {
    recordEvent,
    sync,
    queueLength: computed(() => store.queue.length),
    isSyncing: computed(() => store.syncing),
    isOnline,
  }
}
