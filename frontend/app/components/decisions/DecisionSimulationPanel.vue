<script setup lang="ts">
import type { DecisionSimulationResponse, DecisionSimulationScenario } from "~/types"

const props = defineProps<{ simulation: DecisionSimulationResponse }>()

const scenarios = computed(() => {
  const rows: Array<DecisionSimulationScenario & { tone: "best" | "mid" | "worst" }> = []
  if (props.simulation.recommended) rows.push({ ...props.simulation.recommended, tone: "best" })
  props.simulation.alternatives.forEach((scenario, index) => {
    rows.push({
      ...scenario,
      tone: index === props.simulation.alternatives.length - 1 ? "worst" : "mid",
    })
  })
  return rows.slice(0, 3)
})

const moneyText = (value: number) => {
  const amount = Math.max(0, Math.round(value || 0))
  return amount <= 0 ? "N0 loss" : `about N${amount.toLocaleString()} loss`
}

const scenarioCopy = (scenario: DecisionSimulationScenario) => {
  if (scenario.delay_days <= 0) return `If you act now, you likely avoid ${moneyText(scenario.estimated_revenue_loss)}.`
  if (scenario.label === "Do nothing") return `If you do nothing, you may face ${moneyText(scenario.estimated_revenue_loss)}.`
  return `If you wait ${scenario.delay_days} day${scenario.delay_days === 1 ? "" : "s"}, you may face ${moneyText(scenario.estimated_revenue_loss)}.`
}

const stockoutCopy = (scenario: DecisionSimulationScenario) => {
  if (!scenario.projected_stockout_date) return "Stockout timing stays uncertain."
  const when = new Date(scenario.projected_stockout_date).toLocaleDateString("en-NG", {
    weekday: "short",
    day: "numeric",
    month: "short",
  })
  return `Projected stock after this choice: ${Math.round(scenario.projected_stock)} units. Stockout pressure moves to ${when}.`
}
</script>

<template>
  <section class="sim">
    <div class="sim__head">
      <strong>Compare options</strong>
      <span>Supporting context only</span>
    </div>

    <div class="sim__list">
      <article
        v-for="scenario in scenarios"
        :key="`${scenario.label}-${scenario.delay_days}`"
        class="sim__row"
        :class="`sim__row--${scenario.tone}`"
      >
        <div class="sim__top">
          <span class="sim__label">{{ scenario.label }}</span>
          <strong class="sim__money">{{ moneyText(scenario.estimated_revenue_loss) }}</strong>
        </div>
        <p class="sim__copy">{{ scenarioCopy(scenario) }}</p>
        <p class="sim__meta">{{ stockoutCopy(scenario) }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.sim {
  margin-top: 6px;
  padding: 12px;
  border-radius: var(--r-md);
  border: 1px solid var(--border-subtle);
  background: linear-gradient(180deg, rgba(255,255,255,0.7), rgba(244,247,251,0.92));
}
.sim__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.sim__head strong {
  font-size: 12px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--text);
}
.sim__head span {
  font-size: 11px;
  color: var(--text-4);
}
.sim__list {
  display: grid;
  gap: 8px;
}
.sim__row {
  padding: 10px 11px;
  border-radius: var(--r-sm);
  border: 1px solid transparent;
  transition: transform .18s ease, box-shadow .18s ease;
}
.sim__row:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
.sim__row--best {
  background: rgba(82, 196, 26, 0.08);
  border-color: rgba(82, 196, 26, 0.18);
}
.sim__row--mid {
  background: rgba(250, 173, 20, 0.08);
  border-color: rgba(250, 173, 20, 0.18);
}
.sim__row--worst {
  background: rgba(255, 77, 79, 0.08);
  border-color: rgba(255, 77, 79, 0.18);
}
.sim__top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}
.sim__label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}
.sim__money {
  font-size: 13px;
  font-weight: 800;
  color: var(--text);
}
.sim__copy {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-2);
}
.sim__meta {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-4);
}
</style>
