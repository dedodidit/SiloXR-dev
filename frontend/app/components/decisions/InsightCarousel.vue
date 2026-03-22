<!-- frontend/app/components/decisions/InsightCarousel.vue
     Upgraded with Figma MicroInsights.tsx aesthetic:
     - Dynamic background gradient per insight colour
     - Larger min-height for visual breathing room
     - Colour-coded icon backgrounds
     - Indicator dots that match insight colour
     - Animated background radial gradient
     All API calls and feedback logic unchanged.
-->
<script setup lang="ts">
const { $api } = useNuxtApp()

const insights  = ref<any[]>([])
const current   = ref(0)
const loading   = ref(true)
const paused    = ref(false)
const visible   = ref(true)
let   timer: any = null

onMounted(async () => {
  try { insights.value = await $api<any[]>("/insights/") }
  catch {}
  loading.value = false
  if (insights.value.length > 1) startTimer()
})

onUnmounted(() => clearInterval(timer))

const startTimer = () => {
  timer = setInterval(() => {
    if (!paused.value) advance()
  }, 5000)
}

const advance = () => {
  if (insights.value.length < 2) return
  visible.value = false
  setTimeout(() => {
    current.value = (current.value + 1) % insights.value.length
    visible.value = true
  }, 250)
}

const go = (i: number) => {
  if (i === current.value) return
  visible.value = false
  setTimeout(() => { current.value = i; visible.value = true }, 250)
}

const active = computed(() => insights.value[current.value])

// Severity → brand colour for icon/dot
const severityColor = (sev: string) => ({
  critical: '#FF4D4F',
  warning:  '#FAAD14',
  info:     '#534AB7',
  ok:       '#52C41A',
}[sev] ?? '#534AB7')

const confPct = computed(() => active.value ? Math.round(active.value.confidence * 100) : 0)

const hedgeWord = (conf: number) => {
  if (conf >= 0.70) return "Expected"
  if (conf >= 0.45) return "Likely"
  return "Possibly"
}

// Feedback
const submitFeedback = async (helpful: boolean) => {
  if (!active.value) return
  try {
    await $api("/insights/feedback/", {
      method: "POST",
      body: { product_id: active.value.product_id, detector: active.value.detector, was_helpful: helpful }
    })
  } catch {}
  advance()
}
</script>

<template>
  <div
    class="ic"
    @mouseenter="paused = true"
    @mouseleave="paused = false"
  >

    <!-- Skeleton -->
    <template v-if="loading">
      <div class="ic__skeleton">
        <div class="ic__sk-line ic__sk-line--short" />
        <div class="ic__sk-line ic__sk-line--long" style="margin-top:12px" />
        <div class="ic__sk-line ic__sk-line--medium" style="margin-top:8px" />
        <div class="ic__sk-dots" style="margin-top:20px">
          <div v-for="i in 3" :key="i" class="ic__sk-dot" />
        </div>
      </div>
    </template>

    <!-- Card -->
    <template v-else-if="active">
      <div
        class="ic__card"
        :class="{ 'ic__card--visible': visible }"
      >
        <!-- Dynamic radial gradient background — changes per insight colour -->
        <div
          class="ic__ambient"
          :style="{
            background: `radial-gradient(circle at top right, ${severityColor(active.severity)}18, transparent 65%)`
          }"
          aria-hidden="true"
        />

        <div class="ic__inner">
          <!-- Header row -->
          <div class="ic__header">
            <div class="ic__label-row">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#534AB7" stroke-width="2.5">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
              <span class="ic__eyebrow">Smart Insight</span>
            </div>
            <!-- Confidence hedge badge -->
            <span
              class="ic__hedge"
              :style="{
                color: severityColor(active.severity),
                background: `${severityColor(active.severity)}18`,
                borderColor: `${severityColor(active.severity)}28`,
              }"
            >
              {{ hedgeWord(active.confidence) }}
            </span>
          </div>

          <!-- Product + icon -->
          <div class="ic__product-row">
            <div
              class="ic__icon-wrap"
              :style="{
                background:   `${severityColor(active.severity)}16`,
                borderColor:  `${severityColor(active.severity)}28`,
              }"
            >
              <svg
                width="20" height="20" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2.5"
                :style="{ color: severityColor(active.severity) }"
              >
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            <div>
              <p class="ic__product-name">{{ active.product_name }}</p>
              <p class="ic__product-sku">{{ active.product_sku }}</p>
            </div>
          </div>

          <!-- Observation (main text) -->
          <p class="ic__observation">{{ active.observation }}</p>

          <!-- Recommendation -->
          <p class="ic__rec">{{ active.recommendation }}</p>

          <!-- Date signal -->
          <p v-if="active.date_signal && active.date_signal !== 'at some point'" class="ic__date">
            Expected {{ active.date_signal }}
          </p>

          <!-- Confidence bar -->
          <div class="ic__conf-row">
            <div class="ic__conf-track">
              <div
                class="ic__conf-fill"
                :style="{
                  width:      `${confPct}%`,
                  background: severityColor(active.severity),
                }"
              />
            </div>
            <span class="ic__conf-pct" :style="{ color: severityColor(active.severity) }">
              {{ confPct }}%
            </span>
          </div>

          <!-- Footer -->
          <div class="ic__footer">
            <!-- Dots -->
            <div class="ic__dots">
              <button
                v-for="(ins, i) in insights"
                :key="i"
                class="ic__dot"
                :class="{ 'ic__dot--active': i === current }"
                :style="i === current ? { background: severityColor(ins.severity), width: '20px' } : {}"
                @click="go(i)"
              />
            </div>
            <!-- Feedback -->
            <div class="ic__feedback">
              <span class="ic__feedback-label">Helpful?</span>
              <button class="ic__fb-btn" title="Yes" @click="submitFeedback(true)">👍</button>
              <button class="ic__fb-btn" title="No"  @click="submitFeedback(false)">👎</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Empty -->
    <div v-else class="ic__empty">
      <p>Using similar-business baselines while live signals form.</p>
      <p class="ic__empty-sub">Record stock counts and sales to sharpen these decision signals.</p>
    </div>

  </div>
</template>

<style scoped>
.ic { position: relative; }

/* Skeleton */
.ic__skeleton {
  padding:       24px;
  background:    #fff;
  border-radius: 24px;
  border:        1px solid rgba(0,0,0,0.05);
  min-height:    220px;
}
.ic__sk-line {
  height:        13px;
  border-radius: 99px;
  background:    linear-gradient(90deg, #E8E7E3 25%, #F4F3EF 50%, #E8E7E3 75%);
  background-size: 400px 100%;
  animation:     shimmer 1.6s ease-in-out infinite;
}
.ic__sk-line--short  { width: 90px; }
.ic__sk-line--long   { width: 85%; height: 17px; }
.ic__sk-line--medium { width: 60%; }
.ic__sk-dots { display: flex; gap: 6px; }
.ic__sk-dot  { width: 7px; height: 7px; border-radius: 50%; background: #E8E7E3; }
@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}

/* Card */
.ic__card {
  position:      relative;
  border-radius: 24px;
  background:    #fff;
  border:        1px solid rgba(0,0,0,0.05);
  overflow:      hidden;
  box-shadow:    0 8px 30px rgba(0,0,0,0.06);
  min-height:    220px;
  opacity:       0;
  transform:     translateY(6px);
  transition:    opacity 0.25s ease, transform 0.25s ease, box-shadow 0.3s ease;
}
.ic__card--visible {
  opacity:   1;
  transform: translateY(0);
}
.ic__card:hover { box-shadow: 0 12px 36px rgba(0,0,0,0.09); }

/* Dynamic ambient */
.ic__ambient {
  position:       absolute;
  inset:          0;
  pointer-events: none;
  transition:     background 1s ease;
  opacity:        0.6;
}

.ic__inner { position: relative; padding: 22px 24px; display: flex; flex-direction: column; gap: 12px; }

/* Header */
.ic__header {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  gap:             8px;
}
.ic__label-row { display: flex; align-items: center; gap: 6px; }
.ic__eyebrow {
  font-size:      10px;
  font-weight:    700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color:          rgba(26,26,26,0.45);
}
.ic__hedge {
  font-size:     11px;
  font-weight:   700;
  padding:       3px 10px;
  border-radius: 999px;
  border:        1px solid transparent;
  letter-spacing: 0.04em;
}

/* Product row */
.ic__product-row { display: flex; align-items: flex-start; gap: 12px; }
.ic__icon-wrap {
  flex-shrink:     0;
  width:           44px;
  height:          44px;
  border-radius:   14px;
  border:          1px solid transparent;
  display:         flex;
  align-items:     center;
  justify-content: center;
  transition:      background 0.5s, border-color 0.5s;
}
.ic__product-name { font-size: 14px; font-weight: 700; color: #1A1A1A; }
.ic__product-sku  { font-size: 11px; color: rgba(26,26,26,0.4); letter-spacing: 0.04em; margin-top: 1px; }

/* Text */
.ic__observation { font-size: 15px; font-weight: 600; color: #1A1A1A; line-height: 1.45; }
.ic__rec         { font-size: 13px; color: rgba(26,26,26,0.65); line-height: 1.55; }
.ic__date        { font-size: 12px; color: rgba(26,26,26,0.4); font-style: italic; }

/* Confidence */
.ic__conf-row { display: flex; align-items: center; gap: 10px; }
.ic__conf-track {
  flex:          1;
  height:        6px;
  background:    #E8E7E3;
  border-radius: 999px;
  overflow:      hidden;
}
.ic__conf-fill {
  height:        100%;
  border-radius: 999px;
  transition:    width 0.8s cubic-bezier(0.16,1,0.3,1), background 0.5s;
}
.ic__conf-pct { font-size: 12px; font-weight: 700; min-width: 32px; text-align: right; transition: color 0.5s; }

/* Footer */
.ic__footer { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
.ic__dots { display: flex; gap: 5px; align-items: center; }
.ic__dot {
  width:         7px;
  height:        7px;
  border-radius: 999px;
  background:    #E8E7E3;
  border:        none;
  cursor:        pointer;
  padding:       0;
  transition:    all 0.25s ease;
}
.ic__dot--active { width: 20px; }

.ic__feedback { display: flex; align-items: center; gap: 4px; }
.ic__feedback-label { font-size: 11px; color: rgba(26,26,26,0.35); }
.ic__fb-btn {
  background: none;
  border:     none;
  cursor:     pointer;
  font-size:  15px;
  padding:    3px 4px;
  opacity:    0.6;
  transition: opacity 0.15s, transform 0.15s;
  line-height: 1;
}
.ic__fb-btn:hover { opacity: 1; transform: scale(1.2); }

/* Empty */
.ic__empty {
  padding:       32px;
  text-align:    center;
  font-size:     14px;
  color:         rgba(26,26,26,0.4);
  background:    rgba(244,243,239,0.5);
  border-radius: 24px;
  border:        1px dashed rgba(0,0,0,0.08);
}
</style>
