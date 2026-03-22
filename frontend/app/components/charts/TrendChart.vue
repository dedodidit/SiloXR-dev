<script setup lang="ts">
import type { ForecastStrip } from "~/types"

const props = defineProps<{
  productId: string
  productName: string
  currentQuantity: number
  reorderPoint: number
  forecastStrip?: ForecastStrip[]
  demandDirection?: string
}>()

const canvas = ref<HTMLCanvasElement | null>(null)
let chart: any = null
const chartFailed = ref(false)

const averageConfidence = computed(() => {
  const strips = props.forecastStrip ?? []
  if (!strips.length) return 0.5
  return strips.reduce((sum, item) => sum + (item.confidence_score ?? 0), 0) / strips.length
})
const hasForecast = computed(() => Boolean(props.forecastStrip?.length))
const stockoutHorizon = computed(() => {
  const strips = props.forecastStrip ?? []
  const stockout = strips.find((item) => Number(item.predicted_quantity ?? 0) <= 0)
  return stockout?.days_from_today ?? null
})
const fallbackTitle = computed(() => {
  if (!hasForecast.value) return "We need one verified stock or sales event before SiloXR can draw a live demand curve here."
  return "Forecast data is available, but the chart layer is still loading. The stock signal below is still usable."
})
const fallbackTone = computed(() => {
  if (!hasForecast.value) return "Awaiting the first trusted signal"
  return "Forecast loaded without visual layer"
})
const { chartReady, onCanvas, rebuild } = useChartLoader(() => buildChart())

const buildChart = () => {
  if (!canvas.value || !props.forecastStrip?.length) return
  const Chart = (window as any).Chart
  if (!Chart) return

  const labels = ["Today", ...props.forecastStrip.map(item => `D+${item.days_from_today}`)]
  const central = [props.currentQuantity, ...props.forecastStrip.map(item => item.predicted_quantity)]
  const lower = [props.currentQuantity, ...props.forecastStrip.map(item => item.lower_bound)]
  const upper = [props.currentQuantity, ...props.forecastStrip.map(item => item.upper_bound)]
  const reorder = Array(labels.length).fill(props.reorderPoint)
  const confidenceAlpha = Math.max(0.10, Math.min(0.28, averageConfidence.value * 0.32))

  const stockoutIndex = central.findIndex(value => value <= 0)
  const spikeIndexes = central
    .map((value, index) => ({ value, index }))
    .filter(({ index }) => index > 0 && central[index - 1] - value > Math.max(props.currentQuantity * 0.18, 4))
    .map(({ index }) => index)

  if (chart) {
    chart.destroy()
    chart = null
  }

  chart = new Chart(canvas.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          data: upper,
          fill: "+1",
          backgroundColor: `rgba(83, 74, 183, ${confidenceAlpha.toFixed(2)})`,
          borderColor: "transparent",
          pointRadius: 0,
          tension: 0.35,
        },
        {
          data: lower,
          fill: false,
          borderColor: "transparent",
          pointRadius: 0,
          tension: 0.35,
        },
        {
          label: "Estimated stock",
          data: central,
          borderColor: "#534AB7",
          backgroundColor: "#534AB7",
          borderWidth: 2.5,
          tension: 0.35,
          pointRadius: (ctx: any) => spikeIndexes.includes(ctx.dataIndex) ? 5 : 3,
          pointBackgroundColor: (ctx: any) => spikeIndexes.includes(ctx.dataIndex) ? "#EF9F27" : "#534AB7",
          pointBorderWidth: 2,
          pointBorderColor: "#FFFFFF",
        },
        {
          label: "Reorder point",
          data: reorder,
          borderColor: "#E24B4A",
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 650, easing: "easeOutQuart" },
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
              const value = Math.round(ctx.parsed.y)
              if (ctx.dataset.label === "Reorder point") return ` Reorder point: ${value}`
              if (ctx.dataset.label === "Estimated stock") return ` Estimated stock: ${value}`
              return null
            },
            afterBody: (items: any[]) => {
              const main = items.find((item: any) => item.dataset.label === "Estimated stock")
              if (!main) return []
              return [
                `Range: ${Math.round(lower[main.dataIndex])} to ${Math.round(upper[main.dataIndex])}`,
                spikeIndexes.includes(main.dataIndex) ? "Demand spike detected" : "",
              ].filter(Boolean)
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
          min: 0,
          grid: { color: "rgba(20,20,18,0.05)", drawBorder: false },
          ticks: {
            color: "#A8A69E",
            font: { size: 11 },
            callback: (value: number) => value >= 1000 ? `${(value / 1000).toFixed(1)}k` : `${value}`,
          },
          border: { display: false },
        },
      },
    },
    plugins: [
      {
        id: "stockoutMarker",
        afterDraw(chartRef: any) {
          if (stockoutIndex < 1) return
          const { ctx, scales: { x, y } } = chartRef
          const xPos = x.getPixelForValue(stockoutIndex)
          ctx.save()
          ctx.strokeStyle = "#E24B4A"
          ctx.setLineDash([4, 4])
          ctx.globalAlpha = 0.7
          ctx.beginPath()
          ctx.moveTo(xPos, y.top)
          ctx.lineTo(xPos, y.bottom)
          ctx.stroke()
          ctx.setLineDash([])
          ctx.fillStyle = "#E24B4A"
          ctx.font = "600 10px sans-serif"
          ctx.fillText("Projected stockout", xPos - 34, y.top + 14)
          ctx.restore()
        },
      },
    ],
  })
}

onMounted(async () => {
  await nextTick()
  if (hasForecast.value) {
    setTimeout(() => {
      if (hasForecast.value && !chartReady.value) chartFailed.value = true
    }, 10_500)
  }
})

watch(() => props.forecastStrip, () => {
  chartFailed.value = false
  rebuild()
  if (hasForecast.value) {
    setTimeout(() => {
      if (hasForecast.value && !chartReady.value) chartFailed.value = true
    }, 10_500)
  }
}, { deep: true })

watch(() => props.productId, () => {
  chartFailed.value = false
  rebuild()
})

onUnmounted(() => {
  if (chart) chart.destroy()
})
</script>

<template>
  <div class="tchart surface">
    <div class="tchart__header">
      <div>
        <p class="tchart__title">{{ productName }}</p>
        <p class="tchart__sub">Trend with confidence band, spike detection, and projected stockout markers</p>
      </div>
      <DemandPill v-if="demandDirection" :direction="demandDirection" />
    </div>

    <div class="tchart__legend">
      <span class="tchart__leg-item"><span class="tchart__leg-dot" />Estimated stock</span>
      <span class="tchart__leg-item"><span class="tchart__leg-band" />Uncertainty band</span>
      <span class="tchart__leg-item"><span class="tchart__leg-spike" />Demand spikes</span>
    </div>

    <div class="tchart__wrap">
      <canvas
        v-if="hasForecast && chartReady && !chartFailed"
        :ref="(el) => { canvas = el as HTMLCanvasElement | null; onCanvas(el as HTMLCanvasElement | null) }"
      />
      <div v-else class="tchart__placeholder">
        <div class="tchart__placeholder-metrics">
          <div class="tchart__placeholder-metric">
            <span class="tchart__placeholder-label">Current stock</span>
            <strong>{{ Math.round(currentQuantity || 0) }}</strong>
          </div>
          <div class="tchart__placeholder-metric">
            <span class="tchart__placeholder-label">Reorder point</span>
            <strong>{{ Math.round(reorderPoint || 0) }}</strong>
          </div>
          <div class="tchart__placeholder-metric">
            <span class="tchart__placeholder-label">Forecast horizon</span>
            <strong>{{ stockoutHorizon == null ? "Learning" : `D+${stockoutHorizon}` }}</strong>
          </div>
          <div class="tchart__placeholder-metric">
            <span class="tchart__placeholder-label">Status</span>
            <strong>{{ fallbackTone }}</strong>
          </div>
        </div>
        <p class="tchart__placeholder-copy">
          {{ fallbackTitle }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tchart { padding: 20px 20px 16px; box-shadow: var(--shadow-md); }
.tchart__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.tchart__title { font-size: 15px; font-weight: 700; color: var(--text); }
.tchart__sub { font-size: 11px; color: var(--text-4); margin-top: 3px; }
.tchart__legend { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 14px; }
.tchart__leg-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-3); }
.tchart__leg-dot,
.tchart__leg-spike {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.tchart__leg-dot { background: #534AB7; }
.tchart__leg-spike { background: #EF9F27; }
.tchart__leg-band {
  width: 14px;
  height: 8px;
  border-radius: 3px;
  background: rgba(83, 74, 183, 0.18);
}
.tchart__wrap { height: 250px; position: relative; }
.tchart__placeholder {
  height: 100%;
  border-radius: 16px;
  border: 1px dashed var(--border);
  background: color-mix(in srgb, var(--bg-sunken) 78%, transparent);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
  padding: 20px;
}
.tchart__placeholder-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.tchart__placeholder-metric {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
}
.tchart__placeholder-label {
  display: block;
  font-size: 11px;
  color: var(--text-4);
  text-transform: uppercase;
  letter-spacing: .06em;
}
.tchart__placeholder-metric strong {
  display: block;
  margin-top: 6px;
  font-size: 22px;
  line-height: 1;
  color: var(--text);
}
.tchart__placeholder-copy {
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-3);
}

@media (max-width: 640px) {
  .tchart__placeholder-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
