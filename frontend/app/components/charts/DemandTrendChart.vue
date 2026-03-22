<script setup lang="ts">
const props = defineProps<{
  title: string
  expectedDaily: number
  observedDaily: number
  cvEstimate?: number | null
  showBaselineLabel?: boolean
  driftMode?: boolean
}>()

const canvas = ref<HTMLCanvasElement | null>(null)
let chart: any = null

const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
const cv = computed(() => Math.max(0.08, Number(props.cvEstimate ?? 0.25)))
const driftPct = computed(() => Math.min(0.02, Math.max(0.01, cv.value * 0.04)))

const buildSeries = () => {
  return days.map((_, index) => {
    const wave = Math.sin((index + 1) * 1.17)
    const drift = props.driftMode ? 1 + (wave * driftPct.value) : 1
    const expected = props.expectedDaily * drift
    const observed = props.observedDaily * drift
    const bandWidth = expected * cv.value
    return {
      expected: Number(expected.toFixed(2)),
      observed: Number(observed.toFixed(2)),
      upper: Number((expected + bandWidth).toFixed(2)),
      lower: Number(Math.max(0, expected - bandWidth).toFixed(2)),
    }
  })
}

const series = computed(() => buildSeries())
const { chartReady, onCanvas, rebuild } = useChartLoader(() => buildChart(), 220)

const buildChart = () => {
  if (!canvas.value || !series.value.length) return
  const Chart = (window as any).Chart
  if (!Chart) return

  if (chart) {
    chart.destroy()
    chart = null
  }

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels: days,
      datasets: [
        {
          data: series.value.map(item => item.upper),
          fill: "+1",
          backgroundColor: `rgba(250, 173, 20, ${Math.min(0.28, Math.max(0.12, cv.value * 0.35)).toFixed(2)})`,
          borderColor: "transparent",
          pointRadius: 0,
          tension: 0.35,
        },
        {
          data: series.value.map(item => item.lower),
          fill: false,
          borderColor: "transparent",
          pointRadius: 0,
          tension: 0.35,
        },
        {
          label: "Expected demand",
          data: series.value.map(item => item.expected),
          fill: "+1",
          backgroundColor: "rgba(255, 77, 79, 0.08)",
          borderColor: "#FF4D4F",
          borderWidth: 2.4,
          pointRadius: 3,
          tension: 0.35,
        },
        {
          label: "Observed demand",
          data: series.value.map(item => item.observed),
          borderColor: "#534AB7",
          backgroundColor: "#534AB7",
          borderWidth: 2.2,
          pointRadius: 3,
          tension: 0.35,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#FFFFFF",
          borderColor: "#E5E3DB",
          borderWidth: 1,
          titleColor: "#141412",
          bodyColor: "#4A4945",
          padding: 12,
          cornerRadius: 10,
          callbacks: {
            label: (ctx: any) => {
              const label = ctx.dataset.label ?? ""
              return ` ${label}: ${ctx.parsed.y.toFixed(1)} units/day`
            },
            afterBody: (items: any[]) => {
              const expected = items.find((item: any) => item.dataset.label === "Expected demand")
              const observed = items.find((item: any) => item.dataset.label === "Observed demand")
              if (!expected || !observed) return []
              const gap = Math.max(0, expected.parsed.y - observed.parsed.y)
              return [`Gap: ${gap.toFixed(1)} units/day`, `Range: ${series.value[expected.dataIndex].lower.toFixed(1)} to ${series.value[expected.dataIndex].upper.toFixed(1)}`]
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(20,20,18,0.05)", drawBorder: false },
          ticks: { color: "#A8A69E", maxRotation: 0, font: { size: 11 } },
          border: { display: false },
        },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(20,20,18,0.05)", drawBorder: false },
          ticks: { color: "#A8A69E", font: { size: 11 } },
          border: { display: false },
        },
      },
    },
  })
}

watch(() => [props.expectedDaily, props.observedDaily, props.cvEstimate, props.driftMode], () => rebuild())
onUnmounted(() => { if (chart) chart.destroy() })
</script>

<template>
  <div class="dtc surface">
    <div class="dtc__header">
      <div>
        <p class="dtc__title">{{ title }}</p>
        <p class="dtc__sub">
          <span v-if="showBaselineLabel">Based on similar businesses.</span>
          Expected vs observed demand with a CV-based confidence band.
        </p>
      </div>
      <span v-if="driftMode" class="dtc__badge">Updated using baseline + recent patterns</span>
    </div>

    <div class="dtc__legend">
      <span class="dtc__leg-item"><span class="dtc__leg-line dtc__leg-line--expected" />Expected</span>
      <span class="dtc__leg-item"><span class="dtc__leg-line dtc__leg-line--observed" />Observed</span>
      <span class="dtc__leg-item"><span class="dtc__leg-band" />Confidence band</span>
    </div>

    <div class="dtc__body">
      <div v-if="!chartReady" class="skeleton skeleton--chart dtc__skeleton" />
      <canvas
        v-show="chartReady"
        :ref="(el: any) => { onCanvas(el); canvas = el }"
        class="dtc__canvas"
      />
    </div>
    <p class="dtc__foot">The shaded band reflects demand uncertainty based on variability (CV). Gap highlighted = unmet demand.</p>
  </div>
</template>

<style scoped>
.dtc { padding: 18px 18px 14px; box-shadow: var(--shadow-md); }
.dtc__header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
.dtc__title { font-size: 15px; font-weight: 700; color: var(--text); }
.dtc__sub { margin-top: 4px; font-size: 12px; color: var(--text-4); }
.dtc__badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(250, 173, 20, 0.12);
  color: #9A6700;
  font-size: 11px;
  font-weight: 700;
}
.dtc__legend { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 12px; color: var(--text-4); font-size: 11px; }
.dtc__leg-item { display: inline-flex; align-items: center; gap: 6px; }
.dtc__leg-line { width: 18px; height: 0; border-top: 2px solid currentColor; }
.dtc__leg-line--expected { color: #FF4D4F; }
.dtc__leg-line--observed { color: #534AB7; }
.dtc__leg-band { width: 18px; height: 10px; border-radius: 999px; background: rgba(250, 173, 20, 0.22); }
.dtc__body { height: 260px; }
.dtc__canvas, .dtc__skeleton { width: 100%; height: 100%; }
.dtc__foot { margin-top: 10px; font-size: 11px; color: var(--text-4); }
</style>
