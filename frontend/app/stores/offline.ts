// frontend/app/stores/offline.ts

import { defineStore } from "pinia"

interface QueuedEvent {
  client_event_id: string
  product_id:      string
  event_type:      string
  quantity:        number
  occurred_at:     string
  [key: string]:   unknown
}

export const useOfflineStore = defineStore("offline", () => {
  // Persisted to localStorage so events survive page refresh
  const queue   = ref<QueuedEvent[]>([])
  const syncing = ref(false)

  // Hydrate from localStorage on startup
  if (import.meta.client) {
    const saved = localStorage.getItem("siloxr_offline_queue")
    if (saved) {
      try { queue.value = JSON.parse(saved) } catch { /* ignore */ }
    }
  }

  const persist = () => {
    if (import.meta.client) {
      localStorage.setItem("siloxr_offline_queue", JSON.stringify(queue.value))
    }
  }

  const enqueue = (event: QueuedEvent) => {
    queue.value.push(event)
    persist()
  }

  const clearSynced = (clientIds: string[]) => {
    queue.value = queue.value.filter(
      e => !clientIds.includes(e.client_event_id)
    )
    persist()
  }

  const setSyncing = (val: boolean) => { syncing.value = val }

  return { queue, syncing, enqueue, clearSynced, setSyncing }
})