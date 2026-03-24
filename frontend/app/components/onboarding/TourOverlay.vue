<script setup lang="ts">
const route = useRoute()
const { $api } = useNuxtApp()
const token = useCookie("siloxr_token")
const { preference, initialize: initializeTourPreference } = useTourPreference()

type TourStepDef = {
  target: string
  title: string
  body: string
  placement?: "top" | "bottom" | "left" | "right"
}

const TOUR_SESSIONS: Record<string, TourStepDef[][]> = {
  dashboard: [
    [
      {
        target: ".dashboard-home__greeting",
        title: "This is your home base",
        body: "SiloXR opens with orientation first. Start here to understand the current state of the business before choosing a workspace.",
        placement: "bottom",
      },
      {
        target: ".dashboard-home__status",
        title: "Read the business status simply",
        body: "This card keeps the signal light. A down arrow means pressure is building, an up arrow means operations are steadier, and a dash means we are still learning.",
        placement: "bottom",
      },
      {
        target: ".wlg",
        title: "Choose the workspace that matches your next task",
        body: "Instead of one long dashboard, SiloXR gives you focused workspaces. Open the one that best matches the problem you want to solve right now.",
        placement: "top",
      },
    ],
    [
      {
        target: 'a[href="/workspace/command-center"]',
        title: "Start in command center when you need orientation",
        body: "Use command center when you want the clearest picture of risk, the strongest next move, and the current money posture in one place.",
        placement: "bottom",
      },
      {
        target: 'a[href="/workspace/product-operations"]',
        title: "Use product operations to build stronger signals",
        body: "Record products, stock counts, and sales here. The better your product activity, the stronger SiloXR’s forecasts and decisions become.",
        placement: "bottom",
      },
      {
        target: ".app-header__user",
        title: "Your account controls stay here",
        body: "Open account settings here to manage profile details, notification channels, password changes, and delivery preferences.",
        placement: "right",
      },
    ],
  ],
  "workspace:command-center": [
    [
      {
        target: ".workspace__hero",
        title: "Start with the money signal",
        body: "Command center is the place to begin when you want the clearest picture of what is happening and where money may be exposed.",
        placement: "bottom",
      },
      {
        target: ".workspace__support",
        title: "Follow the next step exactly",
        body: "This panel tells you what to do next. Treat it as the fastest move that improves decision quality or reduces commercial risk.",
        placement: "right",
      },
      {
        target: ".workspace__starter-list, .workspace__empty-actions",
        title: "Use these actions to unlock stronger signals",
        body: "If your business is still early-stage, start with one product and one verified stock or sales event. That is enough to move SiloXR from assumptions toward your real operating pattern.",
        placement: "top",
      },
    ],
  ],
  "workspace:decision-workbench": [
    [
      {
        target: ".workspace__hero",
        title: "This is your decision queue",
        body: "Decision workbench is where SiloXR ranks what matters most. Handle the top recommendation first, then work down the queue by urgency.",
        placement: "bottom",
      },
      {
        target: ".workspace__stack, .empty-state",
        title: "Review decisions with consequence in mind",
        body: "When decisions appear here, they are already filtered for importance. Read the consequence, then act before the cost of waiting grows.",
        placement: "top",
      },
      {
        target: ".workspace__support",
        title: "Execution flow keeps you in order",
        body: "This side panel explains the right sequence: review the top decision, act on it, then clear the remaining queue in priority order.",
        placement: "right",
      },
    ],
  ],
  "workspace:demand-intelligence": [
    [
      {
        target: ".workspace__hero",
        title: "This workspace explains demand",
        body: "Demand intelligence compares what similar businesses are expected to move with what your business is currently showing. It helps you understand where demand may be under-covered.",
        placement: "bottom",
      },
      {
        target: ".workspace__demand-list, .workspace__support",
        title: "Look for the biggest gap first",
        body: "Start with the highest weekly gap. That is usually where unmet demand or missing product coverage is most likely to affect revenue.",
        placement: "top",
      },
      {
        target: ".workspace__panel-copy",
        title: "Use this workspace for explanation, not guesswork",
        body: "This is where SiloXR shows why a gap exists. Use it to understand the signal before you decide whether to add, restock, or verify.",
        placement: "right",
      },
    ],
  ],
  "workspace:product-operations": [
    [
      {
        target: ".workspace__picker",
        title: "Choose one product to work on",
        body: "Product operations is where you focus deeply on one product. Select a product first, then use the forecast, quick actions, and product controls together.",
        placement: "bottom",
      },
      {
        target: ".empty-state, .surface",
        title: "Forecasts need real signals",
        body: "If the forecast strip is empty, SiloXR still needs one more product signal. A stock count or sale event is often enough to activate the next seven-day view.",
        placement: "top",
      },
      {
        target: ".pt",
        title: "Use the product table for quick execution",
        body: "This table is the fastest place to add, subtract, verify, edit, or remove products. Use it to keep the operating picture current without leaving the workspace.",
        placement: "top",
      },
    ],
  ],
}

const userKey = ref("guest")
const sessionsCompleted = ref(0)
const currentStep = ref(0)
const active = ref(false)

const routeKey = computed(() => {
  if (route.path === "/dashboard") return "dashboard"
  if (route.path.startsWith("/workspace/")) {
    const slug = String(route.params.slug ?? "").trim()
    return `workspace:${slug}`
  }
  return ""
})

const routeSessions = computed(() => TOUR_SESSIONS[routeKey.value] ?? [])
const sessionIndex = computed(() => sessionsCompleted.value)
const steps = computed(() => routeSessions.value[sessionIndex.value] ?? [])
const step = computed(() => steps.value[currentStep.value])
const totalInSession = computed(() => steps.value.length)

const storageKeys = computed(() => ({
  sessions: `siloxr_tour_sessions:${userKey.value}:${routeKey.value}`,
  step: `siloxr_tour_step:${userKey.value}:${routeKey.value}`,
}))

const initializeUserKey = async () => {
  if (!token.value) {
    userKey.value = "guest"
    return
  }
  try {
    const me = await $api<{ id?: string; username?: string }>("/auth/me/")
    userKey.value = String(me.id ?? me.username ?? "guest")
  } catch {
    userKey.value = "guest"
  }
}

const initializeRouteTour = () => {
  if (typeof window === "undefined") return
  active.value = false
  currentStep.value = 0
  sessionsCompleted.value = 0

  if (preference.value !== "guided") return
  if (!routeKey.value || routeSessions.value.length === 0) return

  const completed = parseInt(localStorage.getItem(storageKeys.value.sessions) ?? "0", 10)
  const lastStep = parseInt(localStorage.getItem(storageKeys.value.step) ?? "0", 10)
  sessionsCompleted.value = Number.isFinite(completed) ? completed : 0
  currentStep.value = Number.isFinite(lastStep) ? lastStep : 0

  if (sessionsCompleted.value < routeSessions.value.length) {
    setTimeout(() => {
      active.value = true
    }, 800)
  }
}

onMounted(async () => {
  if (typeof window === "undefined") return
  initializeTourPreference()
  await initializeUserKey()
  initializeRouteTour()
})

watch(routeKey, () => {
  if (typeof window === "undefined") return
  initializeRouteTour()
})

watch(preference, () => {
  if (typeof window === "undefined") return
  initializeRouteTour()
})

const next = () => {
  if (currentStep.value < totalInSession.value - 1) {
    currentStep.value += 1
    localStorage.setItem(storageKeys.value.step, String(currentStep.value))
    return
  }
  completeSession()
}

const completeSession = () => {
  const done = sessionsCompleted.value + 1
  sessionsCompleted.value = done
  currentStep.value = 0
  localStorage.setItem(storageKeys.value.sessions, String(done))
  localStorage.setItem(storageKeys.value.step, "0")
  active.value = false
}

const skip = () => {
  localStorage.setItem(storageKeys.value.sessions, String(routeSessions.value.length))
  active.value = false
}
</script>

<template>
  <Transition name="tour-fade">
    <TourStep
      v-if="active && step"
      :key="`${routeKey}-${sessionIndex}-${currentStep}`"
      :target="step.target"
      :title="step.title"
      :body="step.body"
      :step="currentStep + 1"
      :total="totalInSession"
      :placement="step.placement"
      @next="next"
      @skip="skip"
    />
  </Transition>
</template>

<style scoped>
.tour-fade-enter-active { transition: opacity 0.3s ease; }
.tour-fade-leave-active  { transition: opacity 0.2s ease; }
.tour-fade-enter-from, .tour-fade-leave-to { opacity: 0; }
</style>
