<script setup lang="ts">
import type { ForecastStrip, InventoryEventSummary } from "~/types"

const props = defineProps<{
  strips: ForecastStrip[]
  maxQuantity: number
  currentQuantity?: number
  recentEvents?: InventoryEventSummary[] | null | undefined
}>()

const pctWidth = (qty: number) =>
  `${Math.max(6, Math.round((Math.max(qty, 0) / Math.max(props.maxQuantity, 1)) * 100))}%`

const riskTone = (qty: number) => {
  const ratio = qty / Math.max(props.maxQuantity, 1)
  if (ratio > 0.5) return { color: "var(--green)", bg: "rgba(59,109,17,.12)", label: "Low risk" }
  if (ratio > 0.2) return { color: "var(--amber)", bg: "rgba(239,159,39,.14)", label: "Watch" }
  return { color: "var(--red)", bg: "rgba(226,75,74,.14)", label: "Risk" }
}

const headline = computed(() => {
  if (!forecastRows.value.length) return ""
  const last = forecastRows.value[forecastRows.value.length - 1]
  if ((last.quantity ?? 0) <= 0) return "Stock is expected to hit zero inside this projection window."
  if ((last.quantity ?? 0) <= props.maxQuantity * 0.2) return "Stock is trending toward a high-risk level over the next three days."
  if (!hasEnoughObservedSales.value) return "Observed sales are still sparse, so stock is held flat until stronger demand history forms."
  return "Stock stays above risk thresholds across the next three projected days."
})

const fmt = (date: string) => {
  const dt = new Date(date)
  return dt.toLocaleDateString("en", { weekday: "short", day: "numeric" })
}

const dayKey = (date: Date) => date.toISOString().slice(0, 10)

const events = computed(() =>
  [...(props.recentEvents ?? [])].sort(
    (a, b) => new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime(),
  ),
)

const salesByDay = computed(() => {
  const totals = new Map<string, number>()
  for (const event of events.value) {
    if (event.event_type !== "SALE") continue
    const key = dayKey(new Date(event.occurred_at))
    const current = totals.get(key) ?? 0
    const qty = Math.max(0, Math.abs(Number(event.quantity ?? Math.abs(event.signed_quantity ?? 0))))
    totals.set(key, current + qty)
  }
  return totals
})

const observedSalesSeries = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Array.from({ length: 4 }, (_, index) => {
    const date = new Date(today)
    date.setDate(today.getDate() - (3 - index))
    return Number(salesByDay.value.get(dayKey(date)) ?? 0)
  })
})

const nonZeroObservedDays = computed(() => observedSalesSeries.value.filter(value => value > 0))
const hasEnoughObservedSales = computed(() => nonZeroObservedDays.value.length >= 2)

const observedDailySales = computed(() => {
  if (!hasEnoughObservedSales.value) return 0
  return observedSalesSeries.value.reduce((sum, value) => sum + value, 0) / observedSalesSeries.value.length
})

const observedSalesStd = computed(() => {
  if (!hasEnoughObservedSales.value) return 0
  const mean = observedDailySales.value
  const variance = observedSalesSeries.value.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / observedSalesSeries.value.length
  return Math.sqrt(Math.max(0, variance))
})

const historicalPoints = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const current = Math.max(0, Number(props.currentQuantity ?? props.maxQuantity ?? 0))
  const points: Array<{ date: string; quantity: number }> = []
  let running = current

  for (let offset = 0; offset >= -3; offset -= 1) {
    const date = new Date(today)
    date.setDate(today.getDate() + offset)
    const key = dayKey(date)
    if (offset !== 0) {
      const dayEvents = events.filter(event => dayKey(new Date(event.occurred_at)) === dayKey(new Date(date.getTime() + 86400000)))
      const delta = dayEvents.reduce((sum, event) => sum + Number(event.signed_quantity ?? 0), 0)
      running = Math.max(0, running - delta)
    }
    points.push({
      date: date.toISOString(),
      quantity: running,
    })
  }

  return points.reverse()
})

const forecastRows = computed(() => {
  const seed = historicalPoints.value[historicalPoints.value.length - 1]?.quantity ?? Math.max(0, Number(props.currentQuantity ?? 0))
  const futureDates = props.strips.slice(0, 3).map(strip => strip.forecast_date)

  let running = seed
  return Array.from({ length: 3 }, (_, index) => {
    const fallbackDate = new Date()
    fallbackDate.setHours(0, 0, 0, 0)
    fallbackDate.setDate(fallbackDate.getDate() + index + 1)
    const quantity = Math.max(0, running - observedDailySales.value)
    running = quantity

    return {
      date: futureDates[index] ?? fallbackDate.toISOString(),
      quantity,
      lower: Math.max(0, quantity - observedSalesStd.value),
      upper: quantity + observedSalesStd.value,
    }
  })
})

const overlapPoints = computed(() => {
  const forecast = forecastRows.value.map(point => ({
    date: point.date,
    quantity: point.quantity,
    lower: point.lower,
    upper: point.upper,
    isForecast: true,
  }))

  const history = historicalPoints.value.map(point => ({
    date: point.date,
    quantity: point.quantity,
    lower: point.quantity,
    upper: point.quantity,
    isForecast: false,
  }))

  return [...history, ...forecast]
})

const chartMax = computed(() =>
  Math.max(
    1,
    ...overlapPoints.value.map(point => Math.max(point.upper ?? 0, point.quantity ?? 0)),
  ),
)

const chartPoints = computed(() => {
  if (!overlapPoints.value.length) return { expected: "", band: "", history: "" }

  const width = 100
  const height = 120
  const safeMax = chartMax.value
  const xFor = (index: number) => (overlapPoints.value.length === 1 ? 0 : (index / (overlapPoints.value.length - 1)) * width)
  const yFor = (value: number) => height - (Math.max(0, value) / safeMax) * height

  const expected = overlapPoints.value
    .map((point, index) => `${xFor(index)},${yFor(point.quantity ?? 0)}`)
    .join(" ")

  const upper = overlapPoints.value
    .map((point, index) => `${xFor(index)},${yFor(point.upper ?? 0)}`)
    .join(" ")

  const lower = [...overlapPoints.value]
    .reverse()
    .map((point, reverseIndex) => {
      const index = overlapPoints.value.length - 1 - reverseIndex
      return `${xFor(index)},${yFor(point.lower ?? 0)}`
    })
    .join(" ")

  const history = historicalPoints.value
    .map((point, index) => `${xFor(index)},${yFor(point.quantity ?? 0)}`)
    .join(" ")

  return {
    expected,
    history,
    band: `${upper} ${lower}`,
  }
})

const visibleForecastRows = computed(() => forecastRows.value)
</script>

<template>
  <div class="fstrip surface">
    <div class="fstrip__header">
      <div>
        <p class="fstrip__title">Stock projection</p>
        <p class="fstrip__sub">Four historical stock days are followed by three projected days using your current stock and observed sales only. {{ headline }}</p>
      </div>
      <span class="t-hint">Inventory-anchored projection</span>
    </div>

    <div class="fstrip__chart-wrap">
      <svg viewBox="0 0 100 120" preserveAspectRatio="none" class="fstrip__chart">
        <polygon :points="chartPoints.band" class="fstrip__band" />
        <polyline :points="chartPoints.history" class="fstrip__line fstrip__line--history" />
        <polyline :points="chartPoints.expected" class="fstrip__line" />
      </svg>
    </div>

    <div class="fstrip__rows">
      <div v-for="(strip, index) in visibleForecastRows" :key="strip.date" class="fstrip__row">
        <div class="fstrip__meta">
          <strong>{{ fmt(strip.date) }}</strong>
          <span>{{ Math.round(strip.quantity) }} units</span>
        </div>

        <div class="fstrip__bar">
          <div
            class="fstrip__uncertainty"
            :style="{
              width: pctWidth(strip.upper_bound),
              opacity: hasEnoughObservedSales ? 0.22 : 0.12,
            }"
          />
          <div
            class="fstrip__fill"
            :style="{
              width: pctWidth(strip.quantity),
              background: riskTone(strip.quantity).color,
            }"
          />
        </div>

        <span class="fstrip__risk" :style="{ color: riskTone(strip.quantity).color, background: riskTone(strip.quantity).bg }">
          {{ riskTone(strip.quantity).label }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fstrip { padding: 18px 20px; box-shadow: var(--shadow-sm); }
.fstrip__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}
.fstrip__title { font-size: 13px; font-weight: 700; color: var(--text); }
.fstrip__sub { margin-top: 4px; font-size: 12px; color: var(--text-3); max-width: 44ch; }
.fstrip__chart-wrap { margin-bottom: 16px; }
.fstrip__chart {
  width: 100%;
  height: 160px;
  background:
    linear-gradient(to top, transparent 24%, color-mix(in srgb, var(--border-subtle) 65%, transparent) 24%, transparent 25%) center/100% 34%,
    linear-gradient(180deg, color-mix(in srgb, var(--panel) 92%, transparent), color-mix(in srgb, var(--panel) 82%, transparent));
  border: 1px solid var(--border-subtle);
  border-radius: 20px;
  padding: 12px;
}
.fstrip__band {
  fill: color-mix(in srgb, var(--icon-accent) 18%, transparent);
}
.fstrip__line {
  fill: none;
  stroke: var(--icon-accent);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.fstrip__line--history {
  stroke: var(--text);
}
.fstrip__rows { display: flex; flex-direction: column; gap: 10px; }
.fstrip__row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr) 74px;
  gap: 12px;
  align-items: center;
}
.fstrip__meta { display: flex; flex-direction: column; gap: 3px; }
.fstrip__meta strong { font-size: 12px; color: var(--text); }
.fstrip__meta span { font-size: 11px; color: var(--text-4); }
.fstrip__bar {
  position: relative;
  height: 16px;
  background: var(--border-subtle);
  border-radius: 999px;
  overflow: hidden;
}
.fstrip__uncertainty {
  position: absolute;
  inset: 0 auto 0 0;
  background: rgba(83, 74, 183, 0.18);
  border-radius: inherit;
}
.fstrip__fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  transition: width .45s var(--ease-out);
}
.fstrip__risk {
  justify-self: end;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: 999px;
}
@media (max-width: 640px) {
  .fstrip__row {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  .fstrip__risk { justify-self: start; }
}
</style>
