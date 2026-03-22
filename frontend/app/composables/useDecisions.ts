// frontend/app/composables/useDecisions.ts

import type { Decision, DecisionSimulationResponse, ForecastStrip, PortfolioSummary, ReorderRecord } from "~/types"

export const useDecisions = () => {
  const { $api } = useNuxtApp()

  const fetchDecisions = (params?: { active?: boolean; severity?: string }) =>
    $api<{ results: Decision[]; count: number }>("/decisions/", {
      query: {
        active: params?.active ?? true,
        ...(params?.severity ? { severity: params.severity } : {}),
      },
    })

  const acknowledgeDecision = (id: string) =>
    $api<Decision>(`/decisions/${id}/acknowledge/`, { method: "POST" })

  const actDecision = (id: string, body?: { outcome_label?: string; interaction_time_ms?: number }) =>
    $api<Decision>(`/decisions/${id}/act/`, { method: "POST", body })

  const ignoreDecision = (id: string, body?: { interaction_time_ms?: number }) =>
    $api<Decision>(`/decisions/${id}/ignore/`, { method: "POST", body })

  const acknowledgeAll = () =>
    $api<{ acknowledged: number }>("/decisions/acknowledge-all/", {
      method: "POST",
    })

  const fetchTopPriorities = () =>
    $api<Decision[]>("/decisions/top-priorities/")

  const fetchForecastStrip = (productId: string, days = 7) =>
    $api<ForecastStrip[]>("/forecasts/strip/", {
      query: { product: productId, days },
    })

  const fetchAccuracy = (productId: string) =>
    $api(`/forecasts/accuracy/`, { query: { product: productId } })

  const fetchPortfolioSummary = () =>
    $api<PortfolioSummary>("/portfolio/summary/")

  const createReorder = (body: {
    decision_id?: string
    product_id?: string
    suggested_quantity?: number
    suggested_date?: string
    notes?: string
  }) => $api<ReorderRecord>("/reorders/", { method: "POST", body })

  const updateReorder = (id: string, body: { status?: "pending" | "placed" | "received"; notes?: string }) =>
    $api<ReorderRecord>(`/reorders/${id}/`, { method: "PATCH", body })

  const fetchTrustMoment = () =>
    $api("/insights/trust-moment/")

  const fetchDecisionSimulation = (id: string) =>
    $api<DecisionSimulationResponse>(`/decisions/${id}/simulate/`)

  return {
    fetchDecisions,
    acknowledgeDecision,
    actDecision,
    ignoreDecision,
    acknowledgeAll,
    fetchTopPriorities,
    fetchForecastStrip,
    fetchAccuracy,
    fetchPortfolioSummary,
    createReorder,
    updateReorder,
    fetchTrustMoment,
    fetchDecisionSimulation,
  }
}
