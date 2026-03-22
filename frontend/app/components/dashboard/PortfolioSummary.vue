<!-- frontend/app/components/dashboard/PortfolioSummary.vue
     Translated from Figma PortfolioSummary.tsx
     Shows total revenue at risk, products needing action, avg daily risk.
     Props driven by dashboard summary data.
-->
<script setup lang="ts">
const explainOpen = ref(false)

const props = defineProps<{
  revenueAtRisk:       number
  productsAtRisk:      number
  avgDailyRisk?:       number
  totalProducts?:      number
  confidenceScore?:    number
  eyebrow?:            string
  subtitle?:           string
  amountSuffix?:       string
  ctaLabel?:           string
  mode?:               'portfolio' | 'baseline' | 'building'
}>()

const emit = defineEmits<{ review: [] }>()

const confidenceLabel = computed(() => {
  const score = Number(props.confidenceScore ?? 0)
  if (score >= 0.75) return "high"
  if (score >= 0.55) return "moderate"
  return "early"
})

const sourceBasis = computed(() => {
  if (props.mode === "baseline") return "Estimated from similar businesses in your category and size range."
  if (props.mode === "building") return "Using baseline expectations while your own operating pattern forms."
  return "Using your current stock, demand, and forecast signals."
})

const reviewGuidance = computed(() => {
  if (props.mode === "baseline") return "Confirm stock and add missing high-demand lines before treating this as fully personalised risk."
  if (props.mode === "building") return "Record one stock count or sales event to move this view from assumptions to your own operating data."
  return "Review the highest-value products first, then confirm the rest through the decision stack."
})
</script>

<template>
  <div class="ps">
    <!-- Red left border matches Figma -->
    <div class="ps__strip" />

    <div class="ps__body">
      <!-- Decorative blob -->
      <div class="ps__blob" aria-hidden="true" />

      <div class="ps__top">
        <div class="ps__icon-wrap">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="ps__icon">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <div class="ps__heading-group">
          <p class="ps__eyebrow">{{ eyebrow || 'Portfolio at risk' }}</p>
          <h3 class="ps__amount">₦{{ revenueAtRisk.toLocaleString() }}</h3>
          <p class="ps__subtitle">{{ subtitle || 'potential revenue loss this week' }}</p>
        </div>
      </div>

      <div class="ps__metrics">
        <div class="ps__metric ps__metric--red">
          <div class="ps__metric-left">
            <span class="ps__metric-dot ps__metric-dot--pulse" />
            <span class="ps__metric-label">{{ mode === 'baseline' ? 'Products below expected demand' : 'Products needing action' }}</span>
          </div>
          <span class="ps__metric-val ps__metric-val--red">{{ productsAtRisk }}</span>
        </div>

        <div v-if="avgDailyRisk != null && mode !== 'building' && mode !== 'baseline'" class="ps__metric ps__metric--purple">
          <div class="ps__metric-left">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2.5" class="ps__metric-icon">
              <path d="M12 2v20M2 12h20"/>
            </svg>
            <span class="ps__metric-label">{{ mode === 'baseline' ? 'Weekly demand exposure' : 'Avg. daily risk' }}</span>
          </div>
          <span class="ps__metric-val ps__metric-val--purple">₦{{ avgDailyRisk.toLocaleString() }}</span>
        </div>

        <div v-if="totalProducts != null" class="ps__metric ps__metric--neutral">
          <div class="ps__metric-left">
            <span class="ps__metric-label">Total products</span>
          </div>
          <span class="ps__metric-val">{{ totalProducts }}</span>
        </div>

        <div v-if="confidenceScore != null" class="ps__metric ps__metric--neutral">
          <div class="ps__metric-left">
            <span class="ps__metric-label">Confidence score</span>
          </div>
          <span class="ps__metric-val">{{ Math.round(confidenceScore * 100) }}%</span>
        </div>
      </div>

      <div class="ps__trust">
        <button class="ps__trust-toggle" type="button" @click="explainOpen = !explainOpen">
          {{ explainOpen ? 'Hide why this' : 'Why this?' }}
        </button>
        <Transition name="fade">
          <div v-if="explainOpen" class="ps__trust-panel">
            <div class="ps__trust-row">
              <span class="ps__trust-label">Source basis</span>
              <p class="ps__trust-copy">{{ sourceBasis }}</p>
            </div>
            <div class="ps__trust-row">
              <span class="ps__trust-label">Confidence stance</span>
              <p class="ps__trust-copy">{{ Math.round((confidenceScore ?? 0) * 100) }}% ({{ confidenceLabel }})</p>
            </div>
            <div class="ps__trust-row">
              <span class="ps__trust-label">Human review</span>
              <p class="ps__trust-copy">{{ reviewGuidance }}</p>
            </div>
          </div>
        </Transition>
      </div>

      <button class="ps__cta" type="button" @click="emit('review')">
        {{ ctaLabel || 'Review decisions' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.ps {
  position:     relative;
  display:      flex;
  border-radius: 20px;
  overflow:     hidden;
  background:   linear-gradient(145deg, #fff 0%, rgba(255,255,255,0.97) 70%, rgba(255,77,79,0.02) 100%);
  border:       1px solid rgba(255,77,79,0.12);
  box-shadow:   0 8px 30px rgba(0,0,0,0.06);
  transition:   box-shadow 0.3s ease, transform 0.3s ease;
}
.ps:hover {
  box-shadow: 0 12px 40px rgba(0,0,0,0.1);
  transform:  translateY(-2px);
}

.ps__strip {
  width:      4px;
  flex-shrink:0;
  background: linear-gradient(180deg, #FF4D4F 0%, rgba(255,77,79,0.6) 100%);
}
.ps__body {
  flex:     1;
  padding:  24px 24px 24px 20px;
  position: relative;
  overflow: hidden;
}

/* Decorative blur blob */
.ps__blob {
  position:   absolute;
  top:        -20px;
  right:      -20px;
  width:      120px;
  height:     120px;
  background: radial-gradient(circle, rgba(255,77,79,0.08) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.ps__top {
  display:     flex;
  align-items: flex-start;
  gap:         14px;
  margin-bottom: 20px;
}

.ps__icon-wrap {
  flex-shrink:     0;
  width:           44px;
  height:          44px;
  border-radius:   14px;
  background:      linear-gradient(135deg, rgba(255,77,79,0.12) 0%, rgba(255,77,79,0.06) 100%);
  border:          1px solid rgba(255,77,79,0.2);
  display:         flex;
  align-items:     center;
  justify-content: center;
  box-shadow:      0 4px 12px rgba(255,77,79,0.12);
}
.ps__icon { color: #FF4D4F; }

.ps__heading-group { display: flex; flex-direction: column; gap: 2px; }
.ps__eyebrow {
  font-size:      10px;
  font-weight:    700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color:          rgba(26,26,26,0.5);
}
.ps__amount {
  font-size:      32px;
  font-weight:    800;
  letter-spacing: -0.04em;
  color:          #1A1A1A;
  line-height:    1.05;
  margin:         2px 0;
}
.ps__subtitle {
  font-size: 12px;
  color:     rgba(26,26,26,0.5);
}

/* Metric rows */
.ps__metrics { display: flex; flex-direction: column; gap: 8px; }

.ps__metric {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  padding:         12px 14px;
  border-radius:   12px;
}
.ps__metric--red {
  background: linear-gradient(135deg, rgba(255,77,79,0.06) 0%, transparent 100%);
  border:     1px solid rgba(255,77,79,0.12);
}
.ps__metric--purple {
  background: linear-gradient(135deg, rgba(83,74,183,0.06) 0%, transparent 100%);
  border:     1px solid rgba(83,74,183,0.12);
}
.ps__metric--neutral {
  background: rgba(244,243,239,0.6);
  border:     1px solid rgba(0,0,0,0.05);
}

.ps__metric-left {
  display:     flex;
  align-items: center;
  gap:         8px;
}
.ps__metric-dot {
  width:         8px;
  height:        8px;
  border-radius: 50%;
  background:    #FF4D4F;
  flex-shrink:   0;
}
.ps__metric-dot--pulse { animation: ps-pulse 1.8s ease-in-out infinite; }
@keyframes ps-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255,77,79,0.4); }
  50%       { opacity: 0.7; box-shadow: 0 0 0 4px rgba(255,77,79,0); }
}
.ps__metric-icon { color: #534AB7; }
.ps__metric-label { font-size: 13px; font-weight: 500; color: rgba(26,26,26,0.65); }
.ps__metric-val {
  font-size:   20px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color:       #1A1A1A;
}
.ps__metric-val--red    { color: #FF4D4F; }
.ps__metric-val--purple { color: #534AB7; }

.ps__trust {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ps__trust-toggle {
  width: fit-content;
  font-size: 12px;
  font-weight: 700;
  border: 0;
  background: transparent;
  color: rgba(26,26,26,0.58);
  padding: 0;
  cursor: pointer;
}
.ps__trust-panel {
  display: grid;
  gap: 8px;
}
.ps__trust-row {
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.05);
  background: rgba(244,243,239,0.72);
}
.ps__trust-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(26,26,26,0.45);
}
.ps__trust-copy {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: rgba(26,26,26,0.72);
}
.ps__cta {
  margin-top: 14px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #534AB7, #6B62C9);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(83,74,183,0.24);
}
</style>
