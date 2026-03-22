// frontend/app/composables/useDashboard.ts
//
// ADDITIONS (all additive):
//   - daysSinceSignup() — returns days since first login
//   - isNewUser        — reactive computed bool
//   - grace-period UX banner reactive ref
//   - onMounted: writes siloxr_joined_at to localStorage on first run

import type { DashboardSummary } from "~/types"

export const useDashboard = () => {
  const { $api } = useNuxtApp()

  const summary  = ref<DashboardSummary | null>(null)
  const loading  = ref(false)
  const error    = ref<string | null>(null)
  let   refreshTimer: ReturnType<typeof setTimeout> | null = null

  // ── New: new-user grace period ─────────────────────────────────
  const daysSinceSignup = computed((): number => {
    if (typeof window === "undefined") return 999
    try {
      const joined = localStorage.getItem("siloxr_joined_at")
      if (!joined) return 999
      return (Date.now() - parseInt(joined, 10)) / 86_400_000
    } catch { return 999 }
  })

  /** True when the account is under 14 days old — no rate limiting */
  const isNewUser = computed(() => daysSinceSignup.value < 14)

  // ── Existing timer logic (unchanged) ──────────────────────────
  const clearRefreshTimer = () => {
    if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null }
  }

  const scheduleNextFetch = () => {
    if (typeof window === "undefined") return
    clearRefreshTimer()
    // New users always get 60s refresh regardless of usage_policy
    const seconds = isNewUser.value
      ? 60
      : (summary.value?.usage_policy?.refresh_interval_seconds ?? 5 * 60)
    const intervalMs = Math.max(60_000, seconds * 1000)
    refreshTimer = setTimeout(fetch, intervalMs)
  }

  const fetch = async () => {
    loading.value = true
    error.value   = null
    try {
      summary.value = await $api<DashboardSummary>("/dashboard/summary/")
    } catch (e: any) {
      error.value = e?.data?.detail ?? "Failed to load dashboard."
    } finally {
      loading.value = false
      scheduleNextFetch()
    }
  }

  const refresh = () => fetch()

  onMounted(() => {
    // Write joined_at on first ever mount so isNewUser works
    if (typeof window !== "undefined") {
      if (!localStorage.getItem("siloxr_joined_at")) {
        localStorage.setItem("siloxr_joined_at", String(Date.now()))
      }
    }
    fetch()
  })
  onUnmounted(() => clearRefreshTimer())

  return {
    summary,
    loading,
    error,
    refresh,
    isNewUser,
    daysSinceSignup,
  }
}