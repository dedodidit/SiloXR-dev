<script setup lang="ts">
import type { Decision, DecisionSimulationResponse } from "~/types"

const props = defineProps<{ decision: Decision; index?: number }>()
const emit = defineEmits<{ acted: [id: string]; ignored: [id: string]; acknowledge: [id: string] }>()

const store = useDecisionStore()
const { createReorder, fetchDecisionSimulation } = useDecisions()
const expanded = ref(false)
const acting = ref(false)
const ignoring = ref(false)
const feedback = ref("")
const simulationOpen = ref(false)
const simulationLoading = ref(false)
const simulation = ref<DecisionSimulationResponse | null>(null)
const scenarioSaved = ref(false)
const alertArmed = ref(false)

const sev = computed(() => props.decision.severity)
const delay = computed(() => `${(props.index ?? 0) * 60}ms`)

const sevConfig = computed(() => ({
  critical: { strip: "var(--sev-critical-strip)", bg: "var(--sev-critical-bg)", text: "var(--sev-critical-text)", label: "Urgent", pulse: true },
  warning: { strip: "var(--sev-warning-strip)", bg: "var(--sev-warning-bg)", text: "var(--sev-warning-text)", label: "Attention", pulse: false },
  info: { strip: "var(--sev-info-strip)", bg: "var(--sev-info-bg)", text: "var(--sev-info-text)", label: "Check", pulse: false },
  ok: { strip: "var(--sev-ok-strip)", bg: "var(--sev-ok-bg)", text: "var(--sev-ok-text)", label: "Clear", pulse: false },
}[sev.value] ?? {
  strip: "var(--border-strong)",
  bg: "var(--bg-card)",
  text: "var(--text-2)",
  label: "Info",
  pulse: false,
}))

const actionLabel: Record<string, string> = {
  REORDER: "Restock",
  CHECK_STOCK: "Check stock",
  HOLD: "Hold",
  ALERT_LOW: "Monitor",
  ALERT_CRITICAL: "Restock",
  MONITOR: "Monitor",
}

const reasoningPreview = computed(() => {
  const full = props.decision.reasoning || ""
  const dot = full.indexOf(".")
  if (dot > 0) return full.slice(0, dot + 1)
  return full.length > 110 ? `${full.slice(0, 110)}...` : full
})

const impactText = computed(() => {
  const days = Math.max(1, Math.round(props.decision.days_remaining_at_decision ?? 0))
  const lostSales = Math.round(props.decision.estimated_lost_sales ?? 0)
  const revenueLoss = Math.round(props.decision.estimated_revenue_loss ?? 0)
  if (revenueLoss > 0) {
    return `If ignored, you may lose about ${lostSales} sales or ₦${revenueLoss.toLocaleString()} in ${days} days.`
  }
  if (lostSales > 0) {
    return `If ignored, you may lose about ${lostSales} sales in ${days} days.`
  }
  return "This is mainly a verification decision, so the cost of inaction is lower than the cost of stale data."
})

const timeContext = computed(() => {
  const days = props.decision.days_remaining_at_decision
  if (days == null) return "Time context: review on the next inventory check."
  const rounded = Math.max(1, Math.round(days))
  return rounded <= 1
    ? "Time context: today."
    : `Time context: within ${rounded} days.`
})

const suggestedOutcome = computed(() => {
  if (props.decision.action === "CHECK_STOCK") return "verified_stock"
  if (props.decision.action === "ALERT_CRITICAL" || props.decision.action === "ALERT_LOW") return "prevented_stockout"
  if (props.decision.action === "REORDER") return "restocked_in_time"
  return "acted_on_recommendation"
})

const sourceBasis = computed(() => {
  if (props.decision.assumption_message) return props.decision.assumption_message
  if (props.decision.data_stale) return "Using your current stock history with a stale-data penalty until a fresh count is recorded."
  return "Using your recent stock, demand, and forecast pattern."
})

const confidenceStance = computed(() => {
  const score = Number(props.decision.confidence_score ?? 0)
  const label = props.decision.confidence_level ?? (score >= 0.75 ? "high" : score >= 0.55 ? "moderate" : "early")
  if (label === "high") return "High confidence. This recommendation is being driven mostly by your own operating data."
  if (label === "moderate") return "Moderate confidence. The signal is directionally useful but still worth confirming before large action."
  return "Early confidence. This recommendation should be reviewed with a quick stock check before acting."
})

const humanReviewGuidance = computed(() =>
  props.decision.action === "CHECK_STOCK"
    ? "Human review: confirm the current stock position first, then let the system refresh the next decision."
    : "Human review: confirm stock, then act on the recommendation if the shelf position supports it."
)

const decisionSentence = computed(() => {
  const money = Math.round(Number(props.decision.estimated_revenue_loss ?? 0))
  if (money > 0) {
    return `This recommendation is prioritised because about ₦${money.toLocaleString()} is exposed if the current pattern holds.`
  }
  return "This recommendation is prioritised to improve decision quality before money risk rises."
})

const canCompare = computed(() => {
  const confidence = Number(props.decision.confidence_score ?? 0)
  const impact = Number(props.decision.estimated_revenue_loss ?? 0)
  return impact > 1500 && confidence >= 0.5 && confidence <= 0.8
})

const shouldAutoOpenSimulation = computed(() =>
  canCompare.value && props.decision.severity === "critical",
)

const loadSimulation = async () => {
  if (!canCompare.value || simulationLoading.value || simulation.value?.available) return
  simulationLoading.value = true
  try {
    simulation.value = await fetchDecisionSimulation(props.decision.id)
    if (!simulation.value?.available) simulationOpen.value = false
  } finally {
    simulationLoading.value = false
  }
}

const toggleSimulation = async () => {
  if (simulationOpen.value) {
    simulationOpen.value = false
    return
  }
  simulationOpen.value = true
  await loadSimulation()
}

const loadSavedState = () => {
  if (typeof window === "undefined") return
  scenarioSaved.value = window.localStorage.getItem(`siloxr:scenario:${props.decision.id}`) === "saved"
  alertArmed.value = window.localStorage.getItem(`siloxr:alert:${props.decision.id}`) === "armed"
}

const handleSaveScenario = () => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(`siloxr:scenario:${props.decision.id}`, "saved")
  }
  scenarioSaved.value = true
  feedback.value = "Scenario saved. We will keep this comparison ready for your next review."
}

const handleArmAlert = () => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(`siloxr:alert:${props.decision.id}`, "armed")
  }
  alertArmed.value = true
  feedback.value = "Alert saved. This decision will stay easier to revisit as the risk changes."
}

const handleAct = async () => {
  acting.value = true
  try {
    if (["REORDER", "ALERT_CRITICAL", "ALERT_LOW"].includes(props.decision.action)) {
      await createReorder({
        decision_id: props.decision.id,
        suggested_quantity: Math.max(1, Math.round(props.decision.estimated_lost_sales || 1)),
      })
      await store.load()
    } else {
      await store.act(props.decision.id, suggestedOutcome.value)
    }
    feedback.value = props.decision.action === "CHECK_STOCK"
      ? "This decision improved your stock confidence."
      : "Reorder recorded. The feedback loop will track completion."
    emit("acted", props.decision.id)
  } finally {
    acting.value = false
  }
}

const handleIgnore = async () => {
  ignoring.value = true
  try {
    await store.ignore(props.decision.id)
    feedback.value = "Marked as ignored. The system will adjust if the risk changes."
    emit("ignored", props.decision.id)
  } finally {
    ignoring.value = false
  }
}

const handleAcknowledge = async () => {
  await store.acknowledge(props.decision.id)
  emit("acknowledge", props.decision.id)
}

onMounted(async () => {
  loadSavedState()
  if (!shouldAutoOpenSimulation.value) return
  simulationOpen.value = true
  await loadSimulation()
})
</script>

<template>
  <article
    class="dcard animate-fade-up"
    :style="{ '--strip': sevConfig.strip, '--bg': sevConfig.bg, animationDelay: delay }"
    :class="{ 'dcard--pulse': sevConfig.pulse, 'dcard--expanded': expanded }"
  >
    <div class="dcard__strip" />
    <div class="dcard__body">
      <div class="dcard__top">
        <div class="dcard__meta">
          <span class="dcard__sku">{{ decision.product_sku }}</span>
          <span class="dcard__name">{{ decision.product_name }}</span>
        </div>
        <span class="dcard__severity-label" :style="{ color: sevConfig.text, background: sevConfig.bg }">
          {{ sevConfig.label }}
        </span>
      </div>

      <p class="dcard__action" :style="{ color: sevConfig.text }">
        {{ actionLabel[decision.action] ?? decision.action }} {{ decision.product_name.toUpperCase() }}
      </p>

      <div class="dcard__money">
        <span class="dcard__money-label">Money at risk</span>
        <strong class="dcard__money-value">
          {{ decision.estimated_revenue_loss > 0 ? `₦${Math.round(decision.estimated_revenue_loss).toLocaleString()}` : "Verification" }}
        </strong>
      </div>

      <p class="dcard__sentence">{{ decisionSentence }}</p>

      <p class="dcard__reasoning">
        {{ expanded ? decision.reasoning : reasoningPreview }}
      </p>

      <button class="dcard__expand" @click="expanded = !expanded">
        {{ expanded ? "Show less" : "Why this?" }}
      </button>

      <Transition name="fade">
        <div v-if="expanded" class="dcard__trust">
          <div class="dcard__trust-row">
            <span class="dcard__trust-label">Source basis</span>
            <p class="dcard__trust-copy">{{ sourceBasis }}</p>
          </div>
          <div class="dcard__trust-row">
            <span class="dcard__trust-label">Confidence stance</span>
            <p class="dcard__trust-copy">{{ confidenceStance }}</p>
          </div>
          <div class="dcard__trust-row">
            <span class="dcard__trust-label">Human review</span>
            <p class="dcard__trust-copy">{{ humanReviewGuidance }}</p>
          </div>
        </div>
      </Transition>

      <div class="dcard__metrics">
        <ConfidenceBadge :score="decision.confidence_score" />
        <span class="dcard__status">{{ timeContext }}</span>
      </div>

      <p class="dcard__impact">{{ impactText }}</p>

      <div v-if="canCompare" class="dcard__support">
        <button class="dcard__compare" :disabled="simulationLoading" @click="toggleSimulation">
          {{ simulationLoading ? "Loading options..." : (simulationOpen ? "Hide options" : "Compare options") }}
        </button>
        <p class="dcard__support-copy">
          Compare the likely cost of acting now versus waiting, without leaving this decision.
        </p>
      </div>

      <DecisionSimulationPanel
        v-if="simulationOpen && simulation?.available"
        :simulation="simulation"
      />

      <div v-if="simulationOpen || scenarioSaved || alertArmed" class="dcard__stored-value">
        <button class="dcard__stored-btn" :disabled="scenarioSaved" @click="handleSaveScenario">
          {{ scenarioSaved ? "Scenario saved" : "Save scenario" }}
        </button>
        <button class="dcard__stored-btn" :disabled="alertArmed" @click="handleArmAlert">
          {{ alertArmed ? "Alert active" : "Alert me if risk worsens" }}
        </button>
      </div>

      <div v-if="feedback" class="dcard__feedback">
        {{ feedback }}
      </div>

      <div class="dcard__actions">
        <div class="dcard__decision-loop">
          <span class="dcard__loop-label">What should I do?</span>
          <button class="dcard__loop-btn dcard__loop-btn--yes" :disabled="acting || ignoring" @click="handleAct">
            {{ acting ? "Saving..." : (["REORDER", "ALERT_CRITICAL", "ALERT_LOW"].includes(decision.action) ? "Restock now" : "Act on this") }}
          </button>
          <button class="dcard__loop-btn" :disabled="acting || ignoring" @click="handleIgnore">
            {{ ignoring ? "Saving..." : "Ignore" }}
          </button>
        </div>

        <button class="dcard__ack" @click="handleAcknowledge">
          Dismiss
        </button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.dcard {
  display: flex;
  border-radius: var(--r-lg);
  background: var(--bg);
  border: 1px solid var(--border);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}
.dcard--pulse { animation: pulse-card 2.8s var(--ease-in-out) infinite; }
@keyframes pulse-card {
  0%, 100% { box-shadow: var(--shadow-sm); }
  50% { box-shadow: 0 0 0 4px var(--sev-critical-glow), var(--shadow-md); }
}
.dcard__strip { width: 4px; flex-shrink: 0; background: var(--strip); }
.dcard__body { flex: 1; padding: 16px 18px; display: flex; flex-direction: column; gap: 10px; }
.dcard__top { display: flex; justify-content: space-between; gap: 8px; }
.dcard__meta { display: flex; flex-direction: column; gap: 1px; }
.dcard__sku { font-size: 10px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--text-4); }
.dcard__name { font-size: 14px; font-weight: 600; color: var(--text); }
.dcard__severity-label { font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 3px 9px; border-radius: 99px; }
.dcard__action { font-size: 15px; font-weight: 700; line-height: 1.3; }
.dcard__money {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: rgba(255, 77, 79, 0.06);
  border: 1px solid rgba(255, 77, 79, 0.12);
}
.dcard__money-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--text-4);
}
.dcard__money-value {
  font-size: 18px;
  font-weight: 800;
  color: #A33232;
}
.dcard__sentence {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-3);
}
.dcard__reasoning { font-size: 13px; color: var(--text-2); line-height: 1.55; }
.dcard__expand { width: fit-content; font-size: 11px; color: var(--text-3); background: transparent; border: 0; padding: 0; cursor: pointer; }
.dcard__trust {
  display: grid;
  gap: 8px;
}
.dcard__trust-row {
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: rgba(255,255,255,0.66);
  border: 1px solid var(--border-subtle);
}
.dcard__trust-label {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--text-4);
}
.dcard__trust-copy {
  margin-top: 5px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-2);
}
.dcard__metrics { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.dcard__status { font-size: 11px; color: var(--text-4); text-transform: capitalize; }
.dcard__impact { font-size: 12px; line-height: 1.5; color: var(--text-3); background: var(--bg-sunken); border: 1px solid var(--border-subtle); border-radius: var(--r-sm); padding: 10px 12px; }
.dcard__support {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  border: 1px dashed var(--border);
  background: rgba(255,255,255,0.55);
}
.dcard__compare {
  font-size: 12px;
  font-weight: 700;
  padding: 7px 12px;
  border-radius: var(--r-sm);
  border: 1px solid rgba(250, 173, 20, 0.3);
  background: rgba(250, 173, 20, 0.08);
  color: #9A6700;
  cursor: pointer;
}
.dcard__support-copy {
  flex: 1;
  min-width: 220px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-4);
}
.dcard__stored-value {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.dcard__stored-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 7px 12px;
  border-radius: var(--r-sm);
  border: 1px solid rgba(20, 20, 18, 0.1);
  background: rgba(255,255,255,0.72);
  color: var(--text-2);
  cursor: pointer;
}
.dcard__stored-btn:disabled {
  cursor: default;
  opacity: .7;
}
.dcard__feedback { font-size: 12px; color: var(--green); background: var(--green-bg, rgba(59,109,17,.08)); border-radius: var(--r-sm); padding: 8px 10px; }
.dcard__actions { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.dcard__decision-loop { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dcard__loop-label { font-size: 12px; color: var(--text-3); }
.dcard__loop-btn, .dcard__ack {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: var(--r-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  cursor: pointer;
}
.dcard__loop-btn--yes { border-color: rgba(59,109,17,.25); color: #3B6D11; }
.dcard__ack { color: var(--text-3); }
</style>
