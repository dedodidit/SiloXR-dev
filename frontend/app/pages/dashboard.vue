<script setup lang="ts">
import type { DashboardSummary } from "../../types"

const { summary, loading, refresh, daysSinceSignup } = useDashboard()
const dashboardRefreshTick = useState<number>("dashboard-refresh-tick", () => 0)
const now = ref(new Date())

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
  if (statusDirection.value === "dash") return "Business status"
  return statusDirection.value === "down" ? "Business pressure detected" : "Business operating steady"
})

const statusCopy = computed(() => {
  if (statusDirection.value === "dash") {
    return "We are analyzing your business. The first three days stay neutral while early signals form."
  }
  if (statusDirection.value === "down") {
    if (potentialWeeklyGap.value > 0) {
      return `Potential demand gap is tracking at about ${formatNaira(potentialWeeklyGap.value)}/week based on current signals.`
    }
    return `Observed operating risk is currently about ${formatNaira(observedRisk.value)}/week.`
  }
  return "Current signals suggest the business is operating within expected demand coverage."
})

const statusMeta = computed(() => {
  if (statusDirection.value === "dash") return "Early-stage orientation"
  return statusDirection.value === "down" ? "Attention recommended" : "Healthy posture"
})

watch(dashboardRefreshTick, async () => {
  await refresh()
})

let clockTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 60_000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
})

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
          Decision workspaces are ready. Start with the view that matches what you want to resolve next.
        </p>
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
      </div>
    </section>

    <section class="dashboard-home__status surface">
      <div class="dashboard-home__status-copy">
        <p class="dashboard-home__eyebrow">Business status</p>
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
.dashboard-home__status,
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

.dashboard-home__hero-stats {
  display: grid;
  gap: 12px;
  min-width: 180px;
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

.dashboard-home__status-title {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--text);
}

.dashboard-home__status-text {
  margin: 10px 0 0;
  max-width: 56ch;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-3);
}

.dashboard-home__status-meta {
  display: inline-flex;
  margin-top: 14px;
  padding: 7px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-soft) 88%, transparent);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
}

.dashboard-home__status-signal {
  display: inline-flex;
  min-width: 110px;
  min-height: 110px;
  align-items: center;
  justify-content: center;
  border-radius: 30px;
  font-size: 52px;
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
  .dashboard-home__status,
  .dashboard-home__loading {
    padding: 22px;
    border-radius: 22px;
  }

  .dashboard-home__hero-stats {
    grid-template-columns: 1fr;
  }
}
</style>
