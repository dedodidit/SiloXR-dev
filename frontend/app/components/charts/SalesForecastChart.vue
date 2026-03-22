<script setup lang="ts">
import type { BurnRateSummary, InventoryEventSummary } from "~/types"

const props = defineProps<{
  burnRate: BurnRateSummary | null | undefined
  recentEvents?: InventoryEventSummary[] | null | undefined
}>()

const dayKey = (date: Date) => date.toISOString().slice(0, 10)

const recentSalesByDay = computed(() => {
  const sales = new Map<string, number>()
  for (const event of props.recentEvents ?? []) {
    if (event.event_type !== "SALE") continue
    const occurred = new Date(event.occurred_at)
    const key = dayKey(occurred)
    const current = sales.get(key) ?? 0
    const qty = Math.max(0, Math.abs(Number(event.quantity ?? Math.abs(event.signed_quantity ?? 0))))
    sales.set(key, current + qty)
  }
  return sales
})

const hasEnoughSalesHistory = computed(() => recentSalesByDay.value.size >= 2)

const points = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const rate = hasEnoughSalesHistory.value
    ? Math.max(0, Number(props.burnRate?.rate_per_day ?? 0))
    : 0
  const std = hasEnoughSalesHistory.value
    ? Math.max(0, Number(props.burnRate?.std_dev ?? 0))
    : 0

  return Array.from({ length: 7 }, (_, index) => {
    const offset = index - 4
    const date = new Date(today)
    date.setDate(today.getDate() + offset)
    const key = dayKey(date)
    const observed = recentSalesByDay.value.get(key) ?? 0
    const isForecast = offset >= 1

    return {
      date: date.toISOString(),
      label: offset <= 0 ? "Historical" : "Forecast",
      observed,
      expected: isForecast ? rate : observed,
      lower: isForecast ? Math.max(0, rate - std) : observed,
      upper: isForecast ? rate + std : observed,
      isForecast,
    }
  })
})

const chartMax = computed(() =>
  Math.max(1, ...points.value.map(point => Math.max(point.upper, point.expected, point.observed))),
)

const chartPoints = computed(() => {
  const width = 100
  const height = 120
  const safeMax = chartMax.value
  const xFor = (index: number) => (points.value.length === 1 ? 0 : (index / (points.value.length - 1)) * width)
  const yFor = (value: number) => height - (Math.max(0, value) / safeMax) * height

  const expected = points.value.map((point, index) => `${xFor(index)},${yFor(point.expected)}`).join(" ")
  const observed = points.value.map((point, index) => `${xFor(index)},${yFor(point.observed)}`).join(" ")
  const upper = points.value.map((point, index) => `${xFor(index)},${yFor(point.upper)}`).join(" ")
  const lower = [...points.value]
    .reverse()
    .map((point, reverseIndex) => {
      const index = points.value.length - 1 - reverseIndex
      return `${xFor(index)},${yFor(point.lower)}`
    })
    .join(" ")

  return {
    expected,
    observed,
    band: `${upper} ${lower}`,
  }
})

const intro = computed(() => {
  if (!hasEnoughSalesHistory.value) return "Historical sales are still sparse, so forecasted sales are currently shown as zero until more sales are recorded."
  return "Four historical days are shown first, followed by three forecast days built from your recorded sales pattern."
})

const confidenceLabel = computed(() => {
  if (!hasEnoughSalesHistory.value) return "Low confidence"
  const score = Number(props.burnRate?.confidence ?? 0)
  if (score >= 0.8) return "High confidence"
  if (score >= 0.55) return "Moderate confidence"
  return "Early signal"
})

const fmtDay = (date: string) => new Date(date).toLocaleDateString("en", { weekday: "short" })
</script>

<template>
  <div class="sales-forecast surface">
    <div class="sales-forecast__header">
      <div>
        <p class="sales-forecast__eyebrow">Sales forecast</p>
        <h3 class="sales-forecast__title">Four historical days overlapped with three forecast days</h3>
        <p class="sales-forecast__copy">{{ intro }}</p>
      </div>
      <div class="sales-forecast__meta">
        <strong>~{{ Math.round(hasEnoughSalesHistory ? (burnRate?.rate_per_day ?? 0) : 0) }}/day</strong>
        <span>{{ confidenceLabel }}</span>
      </div>
    </div>

    <div class="sales-forecast__chart-wrap">
      <svg viewBox="0 0 100 120" preserveAspectRatio="none" class="sales-forecast__chart">
        <polygon :points="chartPoints.band" class="sales-forecast__band" />
        <polyline :points="chartPoints.observed" class="sales-forecast__line sales-forecast__line--observed" />
        <polyline :points="chartPoints.expected" class="sales-forecast__line" />
      </svg>

      <div class="sales-forecast__days">
        <div v-for="day in points" :key="day.date" class="sales-forecast__day">
          <strong>{{ fmtDay(day.date) }}</strong>
          <span>{{ day.label }}</span>
          <span>{{ day.isForecast ? `~${Math.round(day.expected)} forecast` : `~${Math.round(day.observed)} sold` }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sales-forecast {
  padding: 20px 22px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.sales-forecast__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.sales-forecast__eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.sales-forecast__title {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}
.sales-forecast__copy {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-3);
  max-width: 52ch;
}
.sales-forecast__meta {
  min-width: 120px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.sales-forecast__meta strong {
  font-size: 22px;
  color: var(--text);
}
.sales-forecast__meta span {
  font-size: 12px;
  color: var(--text-3);
}
.sales-forecast__chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.sales-forecast__chart {
  width: 100%;
  height: 160px;
  background:
    linear-gradient(to top, transparent 24%, color-mix(in srgb, var(--border-subtle) 65%, transparent) 24%, transparent 25%) center/100% 34%,
    linear-gradient(180deg, color-mix(in srgb, var(--panel) 92%, transparent), color-mix(in srgb, var(--panel) 82%, transparent));
  border: 1px solid var(--border-subtle);
  border-radius: 20px;
  padding: 12px;
}
.sales-forecast__band {
  fill: color-mix(in srgb, var(--icon-accent) 18%, transparent);
}
.sales-forecast__line {
  fill: none;
  stroke: var(--icon-accent);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.sales-forecast__line--observed {
  stroke: var(--text);
  stroke-dasharray: 0;
}
.sales-forecast__days {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 10px;
}
.sales-forecast__day {
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 10px 8px;
  text-align: center;
  background: color-mix(in srgb, var(--panel) 94%, transparent);
}
.sales-forecast__day strong {
  display: block;
  font-size: 11px;
  color: var(--text);
}
.sales-forecast__day span {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-3);
}
@media (max-width: 720px) {
  .sales-forecast__header {
    flex-direction: column;
  }
  .sales-forecast__meta {
    align-items: flex-start;
  }
  .sales-forecast__days {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
