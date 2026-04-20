<script setup lang="ts">
import type { DashboardSummary } from "../../types"
import { formatMoney } from "../constants/markets"

const { summary, loading, refresh, daysSinceSignup } = useDashboard()
const dashboardRefreshTick = useState<number>("dashboard-refresh-tick", () => 0)
const now = ref(new Date())
const { preference: tourPreference, initialize: initializeTourPreference, setPreference: setTourPreference } = useTourPreference()

const displayName = computed(() => {
  const raw = String(summary.value?.user_context?.name ?? "").trim()
  if (!raw) return "there"
  return raw.charAt(0).toUpperCase() + raw.slice(1)
})

const greeting = computed(() => {
  const hour = now.value.getHours()
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
})

const greetingIcon = computed<"sun" | "sunset" | "moon">(() => {
  const hour = now.value.getHours()
  if (hour < 12) return "sun"
  if (hour < 18) return "sunset"
  return "moon"
})

const demandDeficits = computed(() => summary.value?.demand_deficits ?? [])
const potentialWeeklyGap = computed(() =>
  demandDeficits.value.reduce((sum, item) => sum + Number(item?.revenue_risk_weekly ?? 0), 0)
)
const observedRisk = computed(() => Number(summary.value?.revenue_at_risk_total ?? 0))
const withinNewUserWindow = computed(() => Number(daysSinceSignup.value ?? 999) < 3)
const summaryCurrency = computed(() => String(summary.value?.user_context?.currency || "USD").toUpperCase())
const uploadLimitCopy = computed(() =>
  summary.value?.is_pro
    ? "Unlimited file upload"
    : "Free uploads up to 1MB"
)
const showTourPrompt = computed(() =>
  Number(summary.value?.total_products ?? 0) === 0 && tourPreference.value === "pending"
)
const formatCurrency = (value: number) => formatMoney(value, summaryCurrency.value)
const statusDirection = computed<"down" | "up" | "dash">(() => {
  if (withinNewUserWindow.value) return "dash"
  if (potentialWeeklyGap.value > 0 || observedRisk.value > 0) return "down"
  return "up"
})

const statusLabel = computed(() => {
  if (statusDirection.value === "dash") return "—"
  return statusDirection.value === "down" ? "↓" : "↑"
})

const statusTitle = computed(() => {
  if (statusDirection.value === "dash") return "Signals warming up"
  return statusDirection.value === "down" ? "Business pressure detected" : "Business operating steady"
})

const statusCopy = computed(() => {
  if (statusDirection.value === "dash") {
    return "Your first few days stay neutral while SiloXR builds a read on the business."
  }
  if (statusDirection.value === "down") {
    if (potentialWeeklyGap.value > 0) {
      return `Potential demand gap is tracking at about ${formatCurrency(potentialWeeklyGap.value)}/week based on current signals.`
    }
    return `Observed operating risk is currently about ${formatCurrency(observedRisk.value)}/week.`
  }
  return "Current signals suggest the business is operating within expected demand coverage."
})

const statusMeta = computed(() => {
  if (statusDirection.value === "dash") return "Early stage"
  return statusDirection.value === "down" ? "Attention recommended" : "Healthy posture"
})

watch(dashboardRefreshTick, async () => {
  await refresh()
})

let clockTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  initializeTourPreference()
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 60_000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
})

function skipTour() {
  setTourPreference("skip")
}

function startTour() {
  setTourPreference("guided")
}

function formatNaira(value: number) {
  return `₦${Math.round(value || 0).toLocaleString()}`
}
</script>

<template>
  <div class="dashboard-home">
    <div class="dashboard-home__inner">
    <section class="dashboard-home__hero surface">
      <div class="dashboard-home__hero-copy">
        <div class="dashboard-home__greeting">
          <span class="dashboard-home__greeting-icon" aria-hidden="true">
            <svg
              v-if="greetingIcon === 'sun'"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <circle cx="12" cy="12" r="4.5" />
              <path d="M12 2.5v2.3M12 19.2v2.3M4.8 4.8l1.6 1.6M17.6 17.6l1.6 1.6M2.5 12h2.3M19.2 12h2.3M4.8 19.2l1.6-1.6M17.6 6.4l1.6-1.6" />
            </svg>
            <svg
              v-else-if="greetingIcon === 'sunset'"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M3 18h18" />
              <path d="M7 18a5 5 0 0110 0" />
              <path d="M12 5v4" />
              <path d="M5.5 10.5l1.4 1.1M18.5 10.5l-1.4 1.1M3.5 14H6M18 14h2.5" />
            </svg>
            <svg
              v-else
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M20.5 14.5A8.5 8.5 0 119.5 3.5a7 7 0 0011 11z" />
            </svg>
          </span>
          <div>
            <p class="dashboard-home__eyebrow">Home</p>
            <h1 class="dashboard-home__title">{{ greeting }}, {{ displayName }}</h1>
          </div>
        </div>
        <p class="dashboard-home__subtitle">
          Choose your next move.
        </p>

        <div class="dashboard-home__starter dashboard-home__starter--hero">
          <div class="dashboard-home__starter-copy">
            <p class="dashboard-home__starter-eyebrow">{{ showTourPrompt ? "Get started" : "Quick actions" }}</p>
            <h2 class="dashboard-home__starter-title">
              {{ showTourPrompt ? "Would you like a quick tour?" : "Add products or import data" }}
            </h2>
            <p class="dashboard-home__starter-text">
              {{
                showTourPrompt
                  ? "Take a guided setup, or skip straight to adding your products and sales."
                  : "Manual entry and file import are both ready."
              }}
            </p>
            <span class="dashboard-home__starter-meta">{{ uploadLimitCopy }}</span>
          </div>

          <div v-if="showTourPrompt" class="dashboard-home__tour-choice" role="group" aria-label="Choose a guided tour or skip">
            <button
              type="button"
              class="dashboard-home__tour-choice-card dashboard-home__tour-choice-card--primary"
              @click="startTour"
            >
              <span class="dashboard-home__tour-choice-kicker">Guided path</span>
              <strong>Take the quick tour</strong>
              <span>See how SiloXR works, then jump into products and decisions.</span>
            </button>
            <button
              type="button"
              class="dashboard-home__tour-choice-card dashboard-home__tour-choice-card--secondary"
              @click="skipTour"
            >
              <span class="dashboard-home__tour-choice-kicker">Direct setup</span>
              <strong>Skip guides for now</strong>
              <span>Go straight to adding products, sales, and stock signals yourself.</span>
            </button>
          </div>

          <div class="dashboard-home__starter-actions dashboard-home__starter-actions--compact">
            <NuxtLink to="/onboarding" class="dashboard-home__starter-card dashboard-home__starter-card--primary">
              <span class="dashboard-home__starter-tag">Manual setup</span>
              <strong>Add products and first sales</strong>
            </NuxtLink>
            <NuxtLink to="/upload" class="dashboard-home__starter-card dashboard-home__starter-card--secondary">
              <span class="dashboard-home__starter-tag">File import</span>
              <strong>Upload an Excel or CSV file</strong>
            </NuxtLink>
          </div>
        </div>
      </div>

      <div class="dashboard-home__hero-stats">
        <div class="dashboard-home__mini-stat">
          <span class="dashboard-home__mini-label">Products tracked</span>
          <strong>{{ summary?.total_products ?? 0 }}</strong>
        </div>
        <div class="dashboard-home__mini-stat">
          <span class="dashboard-home__mini-label">Confidence</span>
          <strong>{{ Math.round((summary?.avg_confidence ?? 0) * 100) }}%</strong>
        </div>
        <div class="dashboard-home__status dashboard-home__status--hero">
          <div class="dashboard-home__status-copy">
            <span class="dashboard-home__mini-label">Business status</span>
            <h2 class="dashboard-home__status-title">{{ statusTitle }}</h2>
            <p class="dashboard-home__status-text">{{ statusCopy }}</p>
            <span class="dashboard-home__status-meta">{{ statusMeta }}</span>
          </div>

          <div
            class="dashboard-home__status-signal"
            :class="{
              'dashboard-home__status-signal--down': statusDirection === 'down',
              'dashboard-home__status-signal--up': statusDirection === 'up',
              'dashboard-home__status-signal--dash': statusDirection === 'dash',
            }"
          >
            {{ statusLabel }}
          </div>
        </div>
      </div>
    </section>

    <section class="dashboard-home__workspaces">
      <WorkspaceLauncherGrid
        title="Workspaces"
        hint="Open the operating view that best matches the decision, demand, or product task you want to handle next."
      />
    </section>

    <section v-if="loading" class="dashboard-home__loading surface">
      <span class="dashboard-home__loading-pill" />
      <span class="dashboard-home__loading-line" />
      <span class="dashboard-home__loading-line dashboard-home__loading-line--short" />
    </section>
    </div>
  </div>
</template>

<style scoped>
.dashboard-home {
  width: 100%;
  padding: 28px 24px 42px;
}

.dashboard-home__inner {
  width: min(1180px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 22px;
}

.dashboard-home__hero,
.dashboard-home__starter,
.dashboard-home__loading {
  padding: 28px;
  border-radius: 26px;
  border: 1px solid var(--border-subtle);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 88%, transparent)),
    radial-gradient(circle at top right, color-mix(in srgb, var(--accent, #534ab7) 10%, transparent), transparent 42%);
  box-shadow: var(--shadow-sm);
}

.dashboard-home__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
}

.dashboard-home__greeting {
  display: flex;
  align-items: center;
  gap: 14px;
}

.dashboard-home__greeting-icon {
  display: inline-flex;
  width: 48px;
  height: 48px;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  color: var(--icon-accent);
  background: color-mix(in srgb, var(--icon-accent) 12%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--bg-card) 75%, white 25%);
}

.dashboard-home__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}

.dashboard-home__title {
  margin: 0;
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: var(--text);
}

.dashboard-home__subtitle {
  margin: 14px 0 0;
  max-width: 58ch;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-3);
}

.dashboard-home__starter--hero {
  margin-top: 20px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid color-mix(in srgb, var(--purple) 28%, var(--border-subtle));
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--purple) 13%, var(--bg-card)), color-mix(in srgb, var(--bg-card) 94%, transparent)),
    radial-gradient(circle at top right, color-mix(in srgb, var(--icon-accent) 22%, transparent), transparent 42%),
    radial-gradient(circle at bottom left, color-mix(in srgb, var(--purple) 16%, transparent), transparent 38%);
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--bg-card) 72%, white 28%),
    0 18px 36px color-mix(in srgb, var(--purple) 12%, transparent);
}

.dashboard-home__hero-stats {
  display: grid;
  gap: 12px;
  min-width: 260px;
  align-content: start;
}

.dashboard-home__mini-stat {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 92%, transparent);
}

.dashboard-home__mini-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}

.dashboard-home__mini-stat strong {
  font-size: 20px;
  letter-spacing: -0.02em;
  color: var(--text);
}

.dashboard-home__status {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 20px;
  align-items: center;
}

.dashboard-home__status--hero {
  padding: 16px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--border-subtle) 88%, transparent);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 95%, transparent), color-mix(in srgb, var(--bg-card) 90%, transparent)),
    radial-gradient(circle at top right, color-mix(in srgb, var(--accent, #534ab7) 10%, transparent), transparent 42%);
}

.dashboard-home__status-title {
  margin: 2px 0 0;
  font-size: 20px;
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--text);
}

.dashboard-home__status-text {
  margin: 8px 0 0;
  max-width: 40ch;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-3);
}

.dashboard-home__status-meta {
  display: inline-flex;
  margin-top: 12px;
  padding: 7px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-soft) 88%, transparent);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
}

.dashboard-home__status-signal {
  display: inline-flex;
  min-width: 84px;
  min-height: 84px;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.04em;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 94%, transparent);
}

.dashboard-home__status-signal--down {
  color: var(--danger, #d14a5f);
  background: color-mix(in srgb, var(--danger, #d14a5f) 12%, var(--bg-card));
}

.dashboard-home__status-signal--up {
  color: var(--success, #23956f);
  background: color-mix(in srgb, var(--success, #23956f) 12%, var(--bg-card));
}

.dashboard-home__status-signal--dash {
  color: var(--text-3);
}

.dashboard-home__starter-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.dashboard-home__starter-actions--compact {
  margin-top: 14px;
}

.dashboard-home__tour-choice {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.dashboard-home__tour-choice-card {
  display: grid;
  gap: 6px;
  min-height: 112px;
  padding: 16px 17px;
  border-radius: 18px;
  border: 1px solid transparent;
  text-align: left;
  cursor: pointer;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;
}

.dashboard-home__tour-choice-card strong {
  font-size: 15px;
  line-height: 1.2;
  color: var(--text);
}

.dashboard-home__tour-choice-card span:last-child {
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-2);
}

.dashboard-home__tour-choice-card--primary {
  border-color: color-mix(in srgb, #2D7BD0 34%, var(--border-subtle));
  background:
    linear-gradient(135deg, color-mix(in srgb, #185FA5 18%, var(--bg-card)), color-mix(in srgb, #4AA3FF 22%, var(--bg-card)));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white 48%, transparent),
    0 14px 28px color-mix(in srgb, #185FA5 14%, transparent);
}

.dashboard-home__tour-choice-card--secondary {
  border-color: color-mix(in srgb, #185FA5 18%, var(--border-subtle));
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--bg-card) 94%, transparent), color-mix(in srgb, #185FA5 8%, var(--bg-card)));
}

.dashboard-home__tour-choice-card:hover {
  transform: translateY(-1px);
}

.dashboard-home__tour-choice-kicker {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .11em;
  text-transform: uppercase;
  color: color-mix(in srgb, #185FA5 78%, var(--text-2));
}

.dashboard-home__starter-eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--purple);
}

.dashboard-home__starter-title {
  margin: 0;
  font-size: clamp(24px, 3vw, 28px);
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: var(--text);
}

.dashboard-home__starter-text {
  margin: 10px 0 0;
  max-width: 64ch;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-2);
}

.dashboard-home__starter-meta {
  display: inline-flex;
  margin-top: 14px;
  padding: 8px 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--purple) 14%, transparent);
  color: var(--purple);
  font-size: 12px;
  font-weight: 700;
}

.dashboard-home__starter-card {
  display: grid;
  gap: 4px;
  min-height: 88px;
  padding: 13px 15px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, #185FA5 24%, var(--border-subtle));
  background:
    linear-gradient(135deg, color-mix(in srgb, #185FA5 14%, var(--bg-card)), color-mix(in srgb, #2D7BD0 22%, var(--bg-card)));
  text-decoration: none;
  color: var(--text);
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--bg-card) 64%, white 36%),
    0 10px 22px color-mix(in srgb, #185FA5 10%, transparent);
}

.dashboard-home__starter-card--primary {
  border-color: color-mix(in srgb, #185FA5 32%, var(--border-subtle));
  background:
    linear-gradient(135deg, color-mix(in srgb, #185FA5 20%, var(--bg-card)), color-mix(in srgb, #2D7BD0 28%, var(--bg-card)));
}

.dashboard-home__starter-card--secondary {
  border-color: color-mix(in srgb, #2D7BD0 36%, var(--border-subtle));
  background:
    linear-gradient(135deg, color-mix(in srgb, #2D7BD0 18%, var(--bg-card)), color-mix(in srgb, #4AA3FF 24%, var(--bg-card)));
}

.dashboard-home__starter-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 24px color-mix(in srgb, #185FA5 16%, transparent);
  border-color: color-mix(in srgb, #2D7BD0 44%, var(--border-subtle));
}

.dashboard-home__starter-card strong {
  font-size: 14px;
  line-height: 1.28;
  letter-spacing: -0.01em;
}

.dashboard-home__starter-actions--compact .dashboard-home__starter-card {
  gap: 3px;
}

.dashboard-home__starter-card span:last-child {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-3);
}

.dashboard-home__starter-tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: color-mix(in srgb, #185FA5 78%, var(--text-2));
}

.dashboard-home__loading {
  display: grid;
  gap: 12px;
}

.dashboard-home__loading-pill,
.dashboard-home__loading-line {
  display: block;
  border-radius: 999px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--bg-soft) 86%, transparent), color-mix(in srgb, var(--bg-card) 96%, white 4%), color-mix(in srgb, var(--bg-soft) 86%, transparent));
  background-size: 200% 100%;
  animation: dashboard-home-shimmer 1.2s linear infinite;
}

.dashboard-home__loading-pill {
  width: 132px;
  height: 12px;
}

.dashboard-home__loading-line {
  width: min(560px, 100%);
  height: 14px;
}

.dashboard-home__loading-line--short {
  width: min(320px, 70%);
}

@keyframes dashboard-home-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (max-width: 900px) {
  .dashboard-home__hero,
  .dashboard-home__status {
    grid-template-columns: 1fr;
  }

  .dashboard-home__hero-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-home__starter-actions {
    grid-template-columns: 1fr;
  }

  .dashboard-home__tour-choice {
    grid-template-columns: 1fr;
  }

  .dashboard-home__status-signal {
    min-width: 88px;
    min-height: 88px;
    font-size: 42px;
  }
}

@media (max-width: 640px) {
  .dashboard-home {
    padding: 20px 16px 32px;
  }

  .dashboard-home__hero,
  .dashboard-home__loading {
    padding: 22px;
    border-radius: 22px;
  }

  .dashboard-home__starter--hero {
    padding: 18px;
    border-radius: 22px;
  }

  .dashboard-home__hero-stats {
    grid-template-columns: 1fr;
  }

  .dashboard-home__status--hero {
    padding: 14px;
  }
}
</style>
