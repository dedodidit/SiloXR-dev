// frontend/app/plugins/offline.client.ts

export default defineNuxtPlugin(() => {
  // Load Chart.js from CDN so TrendChart.vue can use it
  if (!(window as any).Chart) {
    const script    = document.createElement("script")
    script.src      = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"
    script.async    = true
    document.head.appendChild(script)
  }
})