<!-- frontend/app/components/decisions/DominantDecision.vue -->

<script setup lang="ts">
const { $api } = useNuxtApp()

const insight  = ref<any>(null)
const loading  = ref(true)
const actedOn  = ref<boolean | null>(null)
const showActed = ref(false)

onMounted(async () => {
  try {
    const data = await $api<{ insight: any }>("/insights/dominant/")
    insight.value = data.insight
  } catch {}
  loading.value = false
})

// ── Confidence-adaptive language ───────────────────────────────────
const hedge = computed(() => {
  const c = insight.value?.confidence ?? 0
  if (c >= 0.70) return { verb: "Expected",   adj: "is expected to" }
  if (c >= 0.45) return { verb: "Likely",     adj: "will likely"    }
  return              { verb: "Possibly",    adj: "may"             }
})

const confPct   = computed(() => Math.round((insight.value?.confidence ?? 0) * 100))
const urgency   = computed(() => insight.value?.urgency_tier ?? "info")
const isPro     = computed(() => insight.value?.is_pro_detail ?? false)

const sevConfig = computed(() => ({
  critical: {
    strip:  "var(--sev-critical-strip)",
    bg:     "var(--sev-critical-bg)",
    text:   "var(--sev-critical-text)",
    label:  "Urgent action needed",
    pulse:  true,
  },
  warning: {
    strip:  "var(--sev-warning-strip)",
    bg:     "var(--sev-warning-bg)",
    text:   "var(--sev-warning-text)",
    label:  "Attention recommended",
    pulse:  false,
  },
  info: {
    strip:  "var(--sev-info-strip)",
    bg:     "var(--sev-info-bg)",
    text:   "var(--sev-info-text)",
    label:  "Worth monitoring",
    pulse:  false,
  },
}[urgency.value] ?? {
  strip: "var(--border-strong)", bg: "var(--bg-card)",
  text: "var(--text-2)", label: "Monitoring", pulse: false,
}))

// ── Action loop: "Did you act?" ────────────────────────────────────
const submitFeedback = async (helpful: boolean) => {
  if (!insight.value) return
  try {
    await $api("/insights/feedback/", {
      method: "POST",
      body: {
        product_id:  insight.value.product_id,
        detector:    insight.value.detector,
        was_helpful: helpful,
      }
    })
  } catch {}
  showActed.value = false
}

const onAcknowledge = () => {
  showActed.value = true
}

// ── Fallback when no dominant insight ─────────────────────────────
const watchItems = [
  "Record stock counts to improve forecast accuracy",
  "Sales patterns take 2 weeks to stabilise — keep recording",
  "Your most urgent products appear at the top of the table",
]
const watchIdx  = ref(0)
let watchTimer: any = null

onMounted(() => {
  watchTimer = setInterval(() => {
    watchIdx.value = (watchIdx.value + 1) % watchItems.length
  }, 6000)
})
onUnmounted(() => clearInterval(watchTimer))
</script>

<template>
  <div class="dd">

    <!-- ── Skeleton ────────────────────────────────────────── -->
    <template v-if="loading">
      <div class="dd__skeleton surface">
        <div class="dd__sk-strip" />
        <div class="dd__sk-body">
          <div class="skeleton skeleton--text" style="width:80px;margin-bottom:10px" />
          <div class="skeleton skeleton--title" style="width:70%" />
          <div class="skeleton skeleton--text" style="width:90%;margin-top:10px" />
          <div class="skeleton skeleton--text" style="width:55%;margin-top:6px" />
        </div>
      </div>
    </template>

    <!-- ── No dominant insight → "Here is what to watch" ──── -->
    <template v-else-if="!insight">
      <div class="dd__watch surface">
        <div class="dd__watch-left">
          <span class="dd__watch-icon">👁</span>
          <div>
            <p class="dd__watch-title">Here is what to watch</p>
            <Transition name="dd-text" mode="out-in">
              <p :key="watchIdx" class="dd__watch-hint">{{ watchItems[watchIdx] }}</p>
            </Transition>
          </div>
        </div>
        <NuxtLink to="/onboarding" class="btn btn-primary btn-sm">
          Add a product →
        </NuxtLink>
      </div>
    </template>

    <!-- ── Dominant insight card ────────────────────────────── -->
    <template v-else>
      <div
        class="dd__card"
        :class="{
          'dd__card--pulse': sevConfig.pulse,
          'dd__card--critical': urgency === 'critical',
        }"
        :style="{ '--dd-strip': sevConfig.strip }"
      >
        <!-- Severity strip -->
        <div class="dd__strip" />

        <div class="dd__body">

          <!-- Label row -->
          <div class="dd__label-row">
            <span class="dd__product-sku">{{ insight.product_sku }}</span>
            <span class="dd__product-name">{{ insight.product_name }}</span>
            <span
              class="dd__urgency-label"
              :style="{ color: sevConfig.text, background: sevConfig.bg }"
            >
              {{ sevConfig.label }}
            </span>
          </div>

          <!-- ① What is happening? ────────────────────────── -->
          <div class="dd__block">
            <span class="dd__block-num">①</span>
            <div>
              <p class="dd__block-label">What is happening</p>
              <p class="dd__block-text" :style="{ color: sevConfig.text }">
                {{ insight.observation }}
              </p>
            </div>
          </div>

          <!-- ② What will happen? ─────────────────────────── -->
          <div class="dd__block">
            <span class="dd__block-num">②</span>
            <div>
              <p class="dd__block-label">What will happen</p>
              <p class="dd__block-text">
                {{ insight.prediction }}
              </p>
              <!-- Date badge — hidden for free users if vague -->
              <span
                v-if="insight.date_signal && insight.date_signal !== 'soon'"
                class="dd__date-badge"
                :style="{ color: sevConfig.text, background: sevConfig.bg }"
              >
                {{ insight.date_signal }}
                <span v-if="!isPro" class="dd__pro-tag">Pro</span>
              </span>
            </div>
          </div>

          <!-- ③ What should I do? ─────────────────────────── -->
          <div class="dd__block dd__block--rec">
            <span class="dd__block-num">③</span>
            <div>
              <p class="dd__block-label">What to do</p>
              <p class="dd__block-text dd__block-text--bold">
                → {{ insight.recommendation }}
              </p>
            </div>
          </div>

          <!-- ④ What happens if I don't? (Pro only) ────────── -->
          <div
            v-if="isPro && insight.impact"
            class="dd__block dd__block--impact"
          >
            <span class="dd__block-num">④</span>
            <div>
              <p class="dd__block-label">If ignored</p>
              <p class="dd__block-text dd__block-text--muted">
                {{ insight.impact }}
              </p>
            </div>
          </div>

          <!-- Pro gate for impact (free users) -->
          <div v-else-if="!isPro" class="dd__impact-gate">
            <span class="dd__impact-gate-text">
              Upgrade to Pro to see the estimated business impact
            </span>
            <NuxtLink to="/billing/upgrade" class="dd__impact-gate-link">Upgrade →</NuxtLink>
          </div>

          <!-- Confidence bar -->
          <div class="dd__conf-row">
            <div class="dd__conf-track">
              <div
                class="dd__conf-fill"
                :style="{
                  width:      `${confPct}%`,
                  background: confPct >= 70 ? 'var(--green)' : confPct >= 45 ? 'var(--amber)' : 'var(--red)',
                }"
              />
            </div>
            <span class="dd__conf-pct">{{ confPct }}%</span>
            <span class="dd__conf-label">confidence</span>
          </div>

          <!-- Action loop -->
          <div v-if="!showActed" class="dd__actions">
            <button class="dd__ack btn btn-secondary btn-sm" @click="onAcknowledge">
              Got it
            </button>
            <button class="dd__fb btn btn-ghost btn-sm" @click="submitFeedback(true)" title="Helpful">
              👍
            </button>
            <button class="dd__fb btn btn-ghost btn-sm" @click="submitFeedback(false)" title="Not useful">
              👎
            </button>
          </div>

          <!-- "Did you act?" follow-up -->
          <div v-else class="dd__acted-prompt">
            <p class="dd__acted-q">Did you act on this?</p>
            <div class="dd__acted-btns">
              <button class="dd__acted-btn dd__acted-btn--yes" @click="submitFeedback(true)">
                Yes, acted
              </button>
              <button class="dd__acted-btn dd__acted-btn--no" @click="submitFeedback(false)">
                Not yet
              </button>
            </div>
          </div>

        </div>
      </div>
    </template>

  </div>
</template>

<style scoped>
.dd { width: 100%; }

/* Skeleton */
.dd__skeleton { display: flex; overflow: hidden; }
.dd__sk-strip { width: 4px; flex-shrink: 0; background: var(--border); }
.dd__sk-body  { flex: 1; padding: 20px 22px; }

/* Watch fallback */
.dd__watch {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  padding:         18px 20px;
  gap:             16px;
  flex-wrap:       wrap;
}
.dd__watch-left  { display: flex; align-items: center; gap: 12px; }
.dd__watch-icon  { font-size: 22px; flex-shrink: 0; }
.dd__watch-title { font-size: 14px; font-weight: 600; color: var(--text); }
.dd__watch-hint  { font-size: 13px; color: var(--text-3); margin-top: 3px; }

/* Text transition */
.dd-text-enter-active, .dd-text-leave-active { transition: opacity .3s; }
.dd-text-enter-from, .dd-text-leave-to       { opacity: 0; }

/* Main card */
.dd__card {
  display:       flex;
  border-radius: var(--r-lg);
  border:        1px solid var(--border);
  background:    var(--bg-card);
  overflow:      hidden;
  box-shadow:    var(--shadow-md);
  transition:    box-shadow var(--dur-base) var(--ease-out);
}
.dd__card:hover { box-shadow: var(--shadow-hover); }

@keyframes dd-pulse {
  0%, 100% { box-shadow: var(--shadow-md); }
  50%       { box-shadow: 0 0 0 5px var(--sev-critical-glow), var(--shadow-md); }
}
.dd__card--pulse { animation: dd-pulse 3s var(--ease-in-out) infinite; }

.dd__strip {
  width:       5px;
  flex-shrink: 0;
  background:  var(--dd-strip, var(--border));
}

.dd__body {
  flex:           1;
  padding:        20px 24px;
  display:        flex;
  flex-direction: column;
  gap:            14px;
}

.dd__label-row {
  display:     flex;
  align-items: center;
  gap:         8px;
  flex-wrap:   wrap;
}
.dd__product-sku {
  font-size:      10px;
  font-weight:    700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color:          var(--text-4);
}
.dd__product-name {
  font-size:   13px;
  font-weight: 600;
  color:       var(--text);
}
.dd__urgency-label {
  margin-left:    auto;
  font-size:      10px;
  font-weight:    700;
  letter-spacing: .05em;
  text-transform: uppercase;
  padding:        3px 10px;
  border-radius:  99px;
  white-space:    nowrap;
}

/* 4-part blocks */
.dd__block {
  display: flex;
  gap:     12px;
  align-items: flex-start;
}
.dd__block-num {
  font-size:   12px;
  font-weight: 700;
  color:       var(--text-4);
  flex-shrink: 0;
  margin-top:  2px;
  min-width:   16px;
}
.dd__block-label {
  font-size:      9px;
  font-weight:    700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color:          var(--text-4);
  margin-bottom:  4px;
}
.dd__block-text {
  font-size:   14px;
  color:       var(--text-2);
  line-height: 1.55;
}
.dd__block-text--bold { font-weight: 600; color: var(--text); }
.dd__block-text--muted { color: var(--text-3); }

.dd__block--rec   { background: var(--purple-bg); border-radius: var(--r-sm); padding: 10px 12px; margin-left: 28px; }
.dd__block--impact { opacity: .85; }

.dd__date-badge {
  display:        inline-flex;
  align-items:    center;
  gap:            6px;
  font-size:      11px;
  font-weight:    600;
  padding:        3px 10px;
  border-radius:  99px;
  margin-top:     6px;
}
.dd__pro-tag {
  font-size:   9px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  background:  var(--purple);
  color:       #fff;
  padding:     1px 5px;
  border-radius: 99px;
}

.dd__impact-gate {
  display:     flex;
  align-items: center;
  gap:         12px;
  padding:     10px 12px;
  background:  var(--bg-sunken);
  border-radius: var(--r-sm);
  border:      1px dashed var(--border-strong);
  flex-wrap:   wrap;
}
.dd__impact-gate-text { font-size: 12px; color: var(--text-3); flex: 1; }
.dd__impact-gate-link {
  font-size:   12px;
  font-weight: 600;
  color:       var(--purple);
  white-space: nowrap;
}

.dd__conf-row {
  display:     flex;
  align-items: center;
  gap:         10px;
  margin-top:  4px;
}
.dd__conf-track {
  flex:          1;
  height:        5px;
  background:    var(--border);
  border-radius: 99px;
  overflow:      hidden;
}
.dd__conf-fill {
  height:        100%;
  border-radius: 99px;
  transition:    width .6s var(--ease-out);
}
.dd__conf-pct   { font-size: 12px; font-weight: 700; color: var(--text-2); min-width: 30px; }
.dd__conf-label { font-size: 11px; color: var(--text-4); }

.dd__actions { display: flex; align-items: center; gap: 8px; }
.dd__ack     { border-color: var(--border-strong); }
.dd__fb      { font-size: 15px; padding: 4px 6px; }

/* "Did you act?" prompt */
.dd__acted-prompt {
  display:     flex;
  align-items: center;
  gap:         12px;
  flex-wrap:   wrap;
}
.dd__acted-q   { font-size: 13px; font-weight: 500; color: var(--text); }
.dd__acted-btns { display: flex; gap: 8px; }
.dd__acted-btn {
  font-size:     12px;
  font-weight:   600;
  padding:       5px 14px;
  border-radius: var(--r-sm);
  border:        1px solid var(--border);
  background:    var(--bg-card);
  cursor:        pointer;
  transition:    all .14s;
}
.dd__acted-btn--yes:hover { background: var(--teal-bg); border-color: var(--teal); color: var(--teal); }
.dd__acted-btn--no:hover  { background: var(--border-subtle); }
</style>