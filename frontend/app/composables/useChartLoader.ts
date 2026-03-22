// frontend/app/composables/useChartLoader.ts
//
// Section 13 — Performance: lazy chart loading.
//
// Chart.js is loaded from CDN (see offline.client.ts plugin).
// This composable:
//   1. Waits for Chart.js to be available via IntersectionObserver
//      (only loads when the canvas is actually visible — true lazy load)
//   2. Provides a debounced rebuild() helper (300ms) so rapid prop
//      changes (product switching, window resize) don't spam chart creation
//   3. Returns `chartReady` reactive bool for skeleton vs canvas display
//
// Usage:
//   const { chartReady, onCanvas, rebuild } = useChartLoader(buildChart)
//   <canvas v-show="chartReady" ref="onCanvas" />
//   <div v-if="!chartReady" class="skeleton skeleton--chart" />

export const useChartLoader = (
  buildFn: () => void,
  debounceMs = 300,
) => {
  const chartReady  = ref(false)
  const canvasEl    = ref<HTMLCanvasElement | null>(null)
  let   debounceTimer: ReturnType<typeof setTimeout> | null = null
  let   observer:      IntersectionObserver | null = null

  // ── Debounced rebuild ─────────────────────────────────────────
  const rebuild = () => {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      if (chartReady.value) buildFn()
    }, debounceMs)
  }

  // ── Canvas ref callback: set up IO when element is mounted ────
  const onCanvas = (el: HTMLCanvasElement | null) => {
    canvasEl.value = el
    if (!el || typeof window === 'undefined') return

    // If Chart.js is already loaded, build immediately
    if ((window as any).Chart) {
      chartReady.value = true
      nextTick(() => buildFn())
      return
    }

    // Use IntersectionObserver to delay loading until in viewport
    observer?.disconnect()
    observer = new IntersectionObserver(entries => {
      if (!entries[0].isIntersecting) return
      observer?.disconnect()
      waitForChart()
    }, { threshold: 0.1 })

    observer.observe(el)
  }

  // ── Poll until Chart.js CDN script has loaded ─────────────────
  const waitForChart = () => {
    if ((window as any).Chart) {
      chartReady.value = true
      nextTick(() => buildFn())
      return
    }
    const poll = setInterval(() => {
      if ((window as any).Chart) {
        clearInterval(poll)
        chartReady.value = true
        nextTick(() => buildFn())
      }
    }, 80)
    // Stop polling after 10s (CDN failure)
    setTimeout(() => clearInterval(poll), 10_000)
  }

  onUnmounted(() => {
    observer?.disconnect()
    if (debounceTimer) clearTimeout(debounceTimer)
  })

  return { chartReady, onCanvas, rebuild }
}