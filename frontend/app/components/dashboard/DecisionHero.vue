<script setup lang="ts">
import type { Decision, Product } from "~/types"

const props = defineProps<{
  decision: Decision | null
  items: Decision[]
  contextProduct?: Product | null
}>()

const emit = defineEmits<{
  focusDecision: [id: string]
  focusProduct: [productId: string]
}>()

const { $api } = useNuxtApp()

// ── Single source of truth: product ─────────────────────────────────
const product = computed(() =>
  props.contextProduct ?? (props.decision as any)?.product ?? null
)

// ── Always-present decision (real or synthetic) ─────────────────────
const derivedDecision = computed(() => {
  if (props.decision) return { ...props.decision, synthetic: false }

  return {
    action: 'CHECK_STOCK',
    synthetic: true
  }
})

// ── Display values ──────────────────────────────────────────────────
const revenue = computed(() =>
  Math.round(props.decision?.estimated_revenue_loss ?? 0)
)

const lostSales = computed(() =>
  Math.round(props.decision?.estimated_lost_sales ?? 0)
)

const days = computed(() => {
  const d = props.decision?.days_remaining_at_decision
  if (d == null) return null
  return Math.max(1, Math.round(d))
})

const conf = computed(() =>
  Math.round((props.decision?.confidence_score ?? 0) * 100)
)

// ── Messaging ───────────────────────────────────────────────────────
const headline = computed(() => {
  if (!props.decision) {
    return "Add a stock update to unlock predictions"
  }

  if (revenue.value > 0) {
    return `₦${revenue.value.toLocaleString()} at risk`
  }

  if (lostSales.value > 0) {
    return `~${lostSales.value} sales at risk`
  }

  return `${props.decision.product_name} needs attention`
})

const subline = computed(() => {
  if (!props.decision) return null

  const d = days.value
  if (d != null && d <= 3) {
    return `${props.decision.product_name} may run out in ~${d} day${d === 1 ? '' : 's'}`
  }

  return `${props.decision.product_name} — action recommended`
})

// ── Actions ─────────────────────────────────────────────────────────
const ACTION_LABEL: Record<string, string> = {
  ALERT_CRITICAL: 'Restock now',
  ALERT_LOW: 'Prepare restock',
  REORDER: 'Place reorder',
  CHECK_STOCK: 'Verify stock',
  MONITOR: 'Monitor closely',
  HOLD: 'No immediate action',
}

const ctaLabel = computed(() => {
  return ACTION_LABEL[derivedDecision.value.action] ?? 'Review'
})

const isCritical = computed(() =>
  props.decision?.severity === 'critical'
)

// ── CTA handler ─────────────────────────────────────────────────────
const acknowledging = ref(false)
const acknowledged = ref(false)

const handleCTA = async () => {
  const decision = derivedDecision.value

  // Synthetic → guide user
  if (decision.synthetic) {
    if (product.value?.id) {
      emit('focusProduct', product.value.id)
    }
    return
  }

  // Real decision → acknowledge
  if (!props.decision || acknowledging.value) return

  acknowledging.value = true
  try {
    await $api(`/decisions/${props.decision.id}/acknowledge/`, {
      method: 'POST'
    })
    acknowledged.value = true
    emit('focusDecision', props.decision.id)
  } catch (e) {
    console.error(e)
  } finally {
    acknowledging.value = false
  }
}
</script>

<template>
  <article
    class="hero"
    :class="{
      'hero--critical': isCritical,
      'hero--no-decision': !decision,
    }"
  >
    <div
      class="hero__urgency-strip"
      :class="isCritical ? 'hero__urgency-strip--critical' : 'hero__urgency-strip--warning'"
    />

    <div class="hero__body">
      <!-- Badge -->
      <div
        class="hero__badge"
        :class="
          isCritical
            ? 'hero__badge--critical'
            : decision
            ? 'hero__badge--warning'
            : 'hero__badge--neutral'
        "
      >
        <span class="hero__badge-text">
          {{
            isCritical
              ? 'URGENT ACTION REQUIRED'
              : decision
              ? 'ATTENTION RECOMMENDED'
              : 'GET STARTED'
          }}
        </span>
      </div>

      <!-- Headline -->
      <h1 class="hero__headline" :class="{ 'hero__headline--muted': !decision }">
        {{ headline }}
        <span v-if="days != null && days <= 3" class="hero__headline-accent">
          in the next {{ days === 1 ? '24 hours' : `${days} days` }}
        </span>
      </h1>

      <!-- Subline -->
      <p v-if="subline" class="hero__subline-text">
        {{ subline }}
      </p>

      <!-- CTA -->
      <button
        class="hero__cta"
        :class="{ 'hero__cta--acknowledged': acknowledged }"
        :disabled="acknowledging"
        @click="handleCTA"
      >
        <span>
          {{
            acknowledged
              ? '✓ Acknowledged'
              : acknowledging
              ? 'Saving…'
              : ctaLabel
          }}
        </span>
      </button>

      <!-- Secondary -->
      <button
        v-if="decision"
        class="hero__secondary"
        @click="emit('focusDecision', decision.id)"
      >
        View full details
      </button>
    </div>
  </article>
</template>

<style scoped>
.hero {
  position:      relative;
  display:       flex;
  border-radius: 24px;
  background:    #fff;
  border:        1px solid rgba(255,77,79,0.1);
  overflow:      hidden;
  box-shadow:    0 8px 30px rgba(0,0,0,0.06);
  transition:    box-shadow 0.5s ease, transform 0.5s ease;
}
.hero:hover {
  box-shadow: 0 12px 40px rgba(0,0,0,0.1);
  transform:  translateY(-1px);
}
.hero--no-decision {
  border-color: rgba(0,0,0,0.05);
  background:   linear-gradient(145deg, #fff, rgba(244,243,239,0.4));
}

/* Urgency strip */
.hero__urgency-strip {
  width:       6px;
  flex-shrink: 0;
}
.hero__urgency-strip--critical {
  background: linear-gradient(180deg, #FF4D4F 0%, rgba(255,77,79,0.7) 60%, #FAAD14 100%);
}
.hero__urgency-strip--warning {
  background: linear-gradient(180deg, #FAAD14 0%, rgba(250,173,20,0.7) 100%);
}

/* Ambient + blob */
.hero__ambient {
  position:   absolute;
  inset:      0;
  background: linear-gradient(135deg,
    rgba(255,77,79,0.02) 0%,
    transparent 50%,
    rgba(250,173,20,0.02) 100%
  );
  opacity:    0;
  transition: opacity 0.5s;
  pointer-events: none;
}
.hero:hover .hero__ambient { opacity: 1; }

.hero__blob {
  position:       absolute;
  top:            24px;
  right:          24px;
  width:          120px;
  height:         120px;
  background:     radial-gradient(circle, rgba(255,77,79,0.06) 0%, rgba(250,173,20,0.04) 50%, transparent 70%);
  border-radius:  50%;
  pointer-events: none;
}

/* Body */
.hero__body {
  flex:           1;
  padding:        32px 36px;
  display:        flex;
  flex-direction: column;
  gap:            20px;
  position:       relative;
}

/* Badge */
.hero__badge {
  display:       inline-flex;
  align-items:   center;
  gap:           7px;
  padding:       6px 14px;
  border-radius: 999px;
  width:         fit-content;
}
.hero__badge--critical {
  background: linear-gradient(90deg, rgba(255,77,79,0.1), rgba(255,77,79,0.05));
  border:     1px solid rgba(255,77,79,0.2);
}
.hero__badge--warning {
  background: linear-gradient(90deg, rgba(250,173,20,0.1), rgba(250,173,20,0.05));
  border:     1px solid rgba(250,173,20,0.2);
}
.hero__badge--neutral {
  background: rgba(244,243,239,0.8);
  border:     1px solid rgba(0,0,0,0.06);
}

.hero__badge-dot {
  width:         7px;
  height:        7px;
  border-radius: 50%;
  background:    #FF4D4F;
  animation:     badge-ping 1.5s ease-in-out infinite;
  flex-shrink:   0;
}
@keyframes badge-ping {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255,77,79,0.5); }
  50%       { box-shadow: 0 0 0 5px rgba(255,77,79,0); }
}
.hero__badge-icon { color: #FF4D4F; flex-shrink: 0; }
.hero__badge-text {
  font-size:      11px;
  font-weight:    700;
  letter-spacing: 0.07em;
  color:          #FF4D4F;
}
.hero__badge--warning .hero__badge-text { color: #FAAD14; }
.hero__badge--neutral .hero__badge-text { color: rgba(26,26,26,0.5); }

/* Headline */
.hero__headline {
  font-size:      clamp(28px, 4vw, 44px);
  font-weight:    800;
  letter-spacing: -0.04em;
  line-height:    1.1;
  color:          #1A1A1A;
}
.hero__headline--muted { color: rgba(26,26,26,0.4); font-size: clamp(20px, 3vw, 28px); }
.hero__headline-accent {
  display: block;
  font-size: 0.7em;
  color: #FF4D4F;
}

/* Subline */
.hero__subline {
  display:       flex;
  align-items:   center;
  gap:           10px;
  padding:       14px 16px;
  background:    rgba(250,173,20,0.05);
  border-radius: 14px;
  border:        1px solid rgba(250,173,20,0.12);
}
.hero__subline-icon {
  flex-shrink:     0;
  width:           32px;
  height:          32px;
  border-radius:   10px;
  background:      #fff;
  display:         flex;
  align-items:     center;
  justify-content: center;
  box-shadow:      0 1px 4px rgba(0,0,0,0.08);
}
.hero__subline-text {
  font-size:   16px;
  color:       #1A1A1A;
  line-height: 1.4;
}
.hero__subline-days {
  font-size:   18px;
  font-weight: 800;
  color:       #FF4D4F;
  margin-left: 4px;
}

/* Recommendation box */
.hero__rec {
  padding:       20px 22px;
  background:    linear-gradient(135deg, rgba(83,74,183,0.06) 0%, rgba(83,74,183,0.02) 100%);
  border-radius: 16px;
  border:        1px solid rgba(83,74,183,0.1);
}
.hero__rec-label {
  font-size:      11px;
  font-weight:    700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color:          rgba(83,74,183,0.6);
  margin-bottom:  8px;
}
.hero__rec-action { display: flex; align-items: center; gap: 10px; }
.hero__rec-arrow {
  width:           34px;
  height:          34px;
  border-radius:   10px;
  background:      #534AB7;
  display:         flex;
  align-items:     center;
  justify-content: center;
  flex-shrink:     0;
  box-shadow:      0 3px 10px rgba(83,74,183,0.3);
}
.hero__rec-text {
  font-size:      26px;
  font-weight:    800;
  color:          #534AB7;
  letter-spacing: -0.02em;
}

/* Confidence + impact grid */
.hero__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap:     16px;
}
.hero__grid-cell {
  padding:       18px 18px 16px;
  border-radius: 16px;
}
.hero__grid-cell--green {
  background: linear-gradient(145deg, rgba(82,196,26,0.07) 0%, transparent 100%);
}
.hero__grid-cell--red {
  background: linear-gradient(145deg, rgba(255,77,79,0.07) 0%, transparent 100%);
}
.hero__grid-cell-head {
  display:       flex;
  align-items:   center;
  gap:           6px;
  margin-bottom: 10px;
  font-size:     11px;
  font-weight:   700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color:         rgba(26,26,26,0.5);
}
.hero__grid-cell-label {
  font-size:     11px;
  font-weight:   700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color:         rgba(26,26,26,0.5);
  margin-bottom: 10px;
}
.hero__grid-cell-val-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px; }
.hero__grid-cell-val {
  font-size:      36px;
  font-weight:    800;
  letter-spacing: -0.04em;
  line-height:    1;
  color:          #1A1A1A;
}
.hero__grid-cell-val--green  { color: #52C41A; }
.hero__grid-cell-val--red    { color: #FF4D4F; }
.hero__grid-cell-val--muted  { color: rgba(26,26,26,0.25); font-size: 24px; }
.hero__grid-cell-sublabel { font-size: 12px; color: rgba(26,26,26,0.5); }

/* Confidence bar */
.hero__conf-track {
  height:        10px;
  background:    #E8E7E3;
  border-radius: 999px;
  overflow:      hidden;
}
.hero__conf-fill {
  height:        100%;
  background:    linear-gradient(90deg, #52C41A, rgba(82,196,26,0.7));
  border-radius: 999px;
  transition:    width 1.2s cubic-bezier(0.16,1,0.3,1);
}

/* CTA */
.hero__cta {
  position:      relative;
  width:         100%;
  padding:       18px 24px;
  border:        none;
  border-radius: 16px;
  background:    linear-gradient(135deg, #534AB7, #6B62C9);
  color:         #fff;
  font-size:     16px;
  font-weight:   700;
  cursor:        pointer;
  overflow:      hidden;
  box-shadow:    0 6px 20px rgba(83,74,183,0.28);
  transition:    transform 0.2s, box-shadow 0.2s;
}
.hero__cta:hover:not(:disabled) {
  transform:  scale(1.015);
  box-shadow: 0 10px 28px rgba(83,74,183,0.38);
}
.hero__cta:active:not(:disabled) { transform: scale(0.985); }
.hero__cta:disabled { opacity: 0.55; cursor: not-allowed; }
.hero__cta--acknowledged { background: linear-gradient(135deg, #52C41A, rgba(82,196,26,0.85)); }

.hero__cta-shimmer {
  position:   absolute;
  inset:      0;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.12) 50%, transparent 100%);
  transform:  translateX(-100%);
}
.hero__cta:hover .hero__cta-shimmer {
  animation: cta-shimmer 0.8s ease forwards;
}
@keyframes cta-shimmer {
  to { transform: translateX(100%); }
}
.hero__cta-content {
  position:    relative;
  display:     flex;
  align-items: center;
  justify-content: center;
  gap:         10px;
}
.hero__cta-arrow { transition: transform 0.2s; }
.hero__cta:hover .hero__cta-arrow { transform: translateX(3px); }

/* Secondary */
.hero__secondary {
  width:         100%;
  padding:       12px;
  background:    none;
  border:        none;
  color:         #534AB7;
  font-size:     14px;
  font-weight:   600;
  cursor:        pointer;
  border-radius: 12px;
  transition:    background 0.15s;
  margin-top:    -4px;
}
.hero__secondary:hover { background: rgba(83,74,183,0.05); }

/* Other items */
.hero__others { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.hero__other {
  display:       flex;
  align-items:   center;
  gap:           10px;
  padding:       10px 14px;
  border-radius: 12px;
  background:    rgba(244,243,239,0.6);
  border:        1px solid rgba(0,0,0,0.04);
  cursor:        pointer;
  text-align:    left;
  width:         100%;
  transition:    background 0.15s;
}
.hero__other:hover { background: rgba(244,243,239,1); }
.hero__other-dot {
  width:         7px;
  height:        7px;
  border-radius: 50%;
  flex-shrink:   0;
}
.hero__other-dot--critical { background: #FF4D4F; }
.hero__other-dot--warning  { background: #FAAD14; }
.hero__other-dot--info     { background: #534AB7; }
.hero__other-dot--ok       { background: #52C41A; }
.hero__other-name  { font-size: 13px; font-weight: 600; color: #1A1A1A; flex: 1; }
.hero__other-action { font-size: 12px; color: rgba(26,26,26,0.5); }
</style>