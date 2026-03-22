<!-- frontend/app/components/shared/RotatingInsights.vue
     Full-width top-of-dashboard rotating insight hero.
     3–6 insights from API, rotate every 4–6s with fade+slide.
     Each insight shows: message, reasoning snippet, confidence hedge.
     Falls back to smart static assumptions when API is empty.
-->
<script setup lang="ts">
const { $api } = useNuxtApp()

// ── Data ──────────────────────────────────────────────────────────
interface Insight {
  id:          string
  observation: string
  recommendation: string
  confidence:  number
  severity:    string
  product_name?: string
  detector?:   string
}

const raw      = ref<Insight[]>([])
const current  = ref(0)
const visible  = ref(true)
const paused   = ref(false)
const loading  = ref(true)
let   timer: any = null
let   interval = 5000

// Smart fallbacks for empty state (Section 5)
const fallbacks: Insight[] = [
  {
    id: 'fb1',
    observation:     'Retail businesses like yours typically sell faster on weekends.',
    recommendation:  'Consider keeping higher stock levels entering Friday.',
    confidence:      0.72,
    severity:        'info',
  },
  {
    id: 'fb2',
    observation:     'Payday spikes are common in the first week of each month.',
    recommendation:  'Review reorder points for high-demand items before month-end.',
    confidence:      0.65,
    severity:        'info',
  },
  {
    id: 'fb3',
    observation:     'Quick stock counts make tomorrow\'s predictions sharper.',
    recommendation:  'Aim for at least one count per product every 3–5 days.',
    confidence:      0.80,
    severity:        'ok',
  },
  {
    id: 'fb4',
    observation:     'Low-confidence forecasts use industry estimates, not your data.',
    recommendation:  'Log your first few sales to unlock personalised predictions.',
    confidence:      0.55,
    severity:        'warning',
  },
]

const insights = computed(() =>
  raw.value.length ? raw.value.slice(0, 6) : fallbacks
)

const active = computed(() => insights.value[current.value])

// ── Load ──────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const data = await $api<Insight[]>('/insights/')
    raw.value = (data ?? []).filter(d => d.observation)
  } catch {}
  loading.value = false
  if (insights.value.length > 1) startTimer()
})
onUnmounted(() => { clearInterval(timer) })

const startTimer = () => {
  timer = setInterval(() => {
    if (!paused.value) advance()
  }, interval)
}

const advance = () => {
  visible.value = false
  setTimeout(() => {
    current.value = (current.value + 1) % insights.value.length
    visible.value = true
  }, 280)
}

const goto = (i: number) => {
  if (i === current.value) return
  visible.value = false
  setTimeout(() => { current.value = i; visible.value = true }, 280)
}

// ── Language hedging ──────────────────────────────────────────────
const hedge = (conf: number) => {
  if (conf >= 0.70) return { word: 'Expected', color: '#52C41A' }
  if (conf >= 0.40) return { word: 'Likely', color: '#FAAD14' }
  return { word: 'Possible', color: '#FF8C42' }
}

// ── Severity → colour ─────────────────────────────────────────────
const sevColor = (sev: string) => ({
  critical: '#FF4D4F',
  warning:  '#FAAD14',
  info:     '#534AB7',
  ok:       '#52C41A',
}[sev] ?? '#534AB7')
</script>

<template>
  <div
    class="ri"
    @mouseenter="paused = true"
    @mouseleave="paused = false"
  >
    <!-- Loading skeleton -->
    <div v-if="loading" class="ri__skeleton">
      <div class="sk-line sk-line--short" />
      <div class="sk-line sk-line--long" style="margin-top:10px" />
      <div class="sk-line sk-line--medium" style="margin-top:8px" />
    </div>

    <template v-else-if="active">
      <!-- Dynamic background tint -->
      <div
        class="ri__bg"
        :style="{ background: `radial-gradient(ellipse at top left, ${sevColor(active.severity)}10 0%, transparent 60%)` }"
        aria-hidden="true"
      />

      <!-- Content -->
      <div class="ri__inner">
        <div class="ri__left">
          <!-- Product + severity badge -->
          <div class="ri__badges">
            <span
              class="ri__sev-badge"
              :style="{ color: sevColor(active.severity), background: `${sevColor(active.severity)}14`, borderColor: `${sevColor(active.severity)}28` }"
            >
              <span
                class="ri__sev-dot"
                :style="{ background: sevColor(active.severity) }"
              />
              {{ active.severity === 'ok' ? 'All clear' : active.severity }}
            </span>
            <span v-if="active.product_name" class="ri__product-chip">{{ active.product_name }}</span>
          </div>

          <!-- Observation headline -->
          <Transition name="ri-fade" mode="out-in">
            <div :key="current" :class="{ 'ri__content--visible': visible }">
              <p class="ri__observation">{{ active.observation }}</p>
              <p class="ri__rec">{{ active.recommendation }}</p>
            </div>
          </Transition>
        </div>

        <div class="ri__right">
          <!-- Confidence meter -->
          <div class="ri__conf">
            <div
              class="ri__conf-ring"
              :style="{ '--pct': active.confidence, '--color': hedge(active.confidence).color }"
            >
              <span class="ri__conf-val" :style="{ color: hedge(active.confidence).color }">
                {{ Math.round(active.confidence * 100) }}%
              </span>
            </div>
            <div class="ri__conf-labels">
              <span class="ri__conf-word" :style="{ color: hedge(active.confidence).color }">
                {{ hedge(active.confidence).word }}
              </span>
              <span class="ri__conf-sub">Confidence</span>
            </div>
          </div>

          <!-- Dots -->
          <div class="ri__dots">
            <button
              v-for="(ins, i) in insights"
              :key="i"
              class="ri__dot"
              :class="{ 'ri__dot--active': i === current }"
              :style="i === current ? { background: sevColor(ins.severity) } : {}"
              :aria-label="`Insight ${i + 1}`"
              @click="goto(i)"
            />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ri {
  position:      relative;
  border-radius: 20px;
  background:    #fff;
  border:        1px solid rgba(0,0,0,0.05);
  box-shadow:    0 4px 20px rgba(0,0,0,0.06);
  overflow:      hidden;
  min-height:    120px;
  transition:    box-shadow 0.3s;
}
.ri:hover { box-shadow: 0 8px 30px rgba(0,0,0,0.09); }

.ri__bg {
  position:       absolute;
  inset:          0;
  pointer-events: none;
  transition:     background 0.8s ease;
}

.ri__inner {
  position:    relative;
  display:     flex;
  align-items: center;
  gap:         24px;
  padding:     22px 26px;
}

.ri__left  { flex: 1; min-width: 0; }
.ri__right { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: 16px; }

/* Badges */
.ri__badges { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.ri__sev-badge {
  display:        inline-flex;
  align-items:    center;
  gap:            5px;
  padding:        4px 10px;
  border-radius:  999px;
  font-size:      11px;
  font-weight:    700;
  letter-spacing: 0.05em;
  text-transform: capitalize;
  border:         1px solid transparent;
}
.ri__sev-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.ri__product-chip {
  padding:       3px 9px;
  background:    rgba(83,74,183,0.08);
  border-radius: 999px;
  font-size:     11px;
  font-weight:   600;
  color:         #534AB7;
}

/* Text */
.ri__observation {
  font-size:      18px;
  font-weight:    700;
  color:          #1A1A1A;
  line-height:    1.35;
  letter-spacing: -0.01em;
  margin-bottom:  6px;
}
.ri__rec {
  font-size:   13px;
  color:       rgba(26,26,26,0.6);
  line-height: 1.55;
}

/* Confidence ring */
.ri__conf { display: flex; align-items: center; gap: 10px; }
.ri__conf-ring {
  width:           64px;
  height:          64px;
  border-radius:   50%;
  background:      conic-gradient(
    var(--color) calc(var(--pct) * 360deg),
    #E8E7E3 0deg
  );
  display:         flex;
  align-items:     center;
  justify-content: center;
  flex-shrink:     0;
  position:        relative;
}
.ri__conf-ring::after {
  content:       "";
  position:      absolute;
  inset:         6px;
  border-radius: 50%;
  background:    #fff;
}
.ri__conf-val {
  font-size:   14px;
  font-weight: 800;
  position:    relative;
  z-index:     1;
}
.ri__conf-labels { display: flex; flex-direction: column; gap: 2px; }
.ri__conf-word { font-size: 13px; font-weight: 700; }
.ri__conf-sub  { font-size: 11px; color: rgba(26,26,26,0.45); }

/* Dots */
.ri__dots { display: flex; gap: 5px; }
.ri__dot {
  width:         6px;
  height:        6px;
  border-radius: 50%;
  background:    #E8E7E3;
  border:        none;
  cursor:        pointer;
  padding:       0;
  transition:    width 0.2s, background 0.2s;
}
.ri__dot--active { width: 16px; border-radius: 3px; }

/* Skeleton */
.ri__skeleton { padding: 22px 26px; }
.sk-line { height: 14px; border-radius: 8px; background: linear-gradient(90deg, #E8E7E3 25%, #F4F3EF 50%, #E8E7E3 75%); background-size: 400px; animation: shimmer 1.4s ease infinite; }
.sk-line--short  { width: 80px; }
.sk-line--long   { width: 80%; height: 22px; }
.sk-line--medium { width: 55%; }
@keyframes shimmer { 0% { background-position: -400px; } 100% { background-position: 400px; } }

/* Transition */
.ri-fade-enter-active { transition: opacity 0.28s ease, transform 0.28s ease; }
.ri-fade-leave-active  { transition: opacity 0.2s ease, transform 0.2s ease; }
.ri-fade-enter-from    { opacity: 0; transform: translateY(6px); }
.ri-fade-leave-to      { opacity: 0; transform: translateY(-4px); }

@media (max-width: 640px) {
  .ri__inner { flex-direction: column; align-items: flex-start; gap: 16px; }
  .ri__right { flex-direction: row; width: 100%; justify-content: space-between; }
  .ri__observation { font-size: 16px; }
}
</style>