// frontend/app/stores/decisions.ts

import { defineStore } from "pinia"
import type { Decision } from "~/types"

export const useDecisionStore = defineStore("decisions", () => {
  const decisions   = ref<Decision[]>([])
  const loading     = ref(false)
  const topPriorities = ref<Decision[]>([])

  const {
    fetchDecisions,
    acknowledgeDecision,
    acknowledgeAll,
    actDecision,
    ignoreDecision,
    fetchTopPriorities,
  } = useDecisions()

  const load = async () => {
    loading.value = true
    try {
      const res       = await fetchDecisions({ active: true })
      decisions.value = res.results
      topPriorities.value = await fetchTopPriorities().catch(() => [])
    } finally {
      loading.value = false
    }
  }

  const acknowledge = async (id: string) => {
    await acknowledgeDecision(id)
    decisions.value = decisions.value.filter(d => d.id !== id)
  }

  const acknowledgeAllActive = async () => {
    await acknowledgeAll()
    decisions.value = []
    topPriorities.value = []
  }

  const act = async (id: string, outcome_label?: string) => {
    const updated = await actDecision(id, { outcome_label })
    decisions.value = decisions.value.filter(d => d.id !== id)
    topPriorities.value = topPriorities.value.filter(d => d.id !== id)
    return updated
  }

  const ignore = async (id: string) => {
    const updated = await ignoreDecision(id)
    decisions.value = decisions.value.filter(d => d.id !== id)
    topPriorities.value = topPriorities.value.filter(d => d.id !== id)
    return updated
  }

  const critical = computed(() =>
    decisions.value.filter(d => d.severity === "critical")
  )
  const warnings = computed(() =>
    decisions.value.filter(d => d.severity === "warning")
  )
  const count = computed(() => decisions.value.length)

  return {
    decisions, topPriorities, loading,
    load, acknowledge, acknowledgeAllActive, act, ignore,
    critical, warnings, count,
  }
})
