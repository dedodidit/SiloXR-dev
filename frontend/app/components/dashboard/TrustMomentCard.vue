<!-- frontend/app/components/dashboard/TrustMomentCard.vue
     Translated from Figma TrustMomentCard.tsx.
     Surfaces the FeedbackEngine's verified prediction moments.
     "We predicted X. It happened." — the trust-building card.
-->
<script setup lang="ts">
const props = defineProps<{
  productName:   string
  predictedDays: number
  actualDays:    number
  accuracyPct?:  number
  date?:         string
}>()

const isExact = computed(() =>
  Math.abs(props.predictedDays - props.actualDays) <= 0.5
)

const accuracyLabel = computed(() => {
  if (props.accuracyPct != null) return `${Math.round(props.accuracyPct)}% match`
  return isExact.value ? '100% match' : `${Math.round(100 - Math.abs(props.predictedDays - props.actualDays) / props.predictedDays * 100)}% match`
})
</script>

<template>
  <div class="tmc">
    <!-- Decorative blobs -->
    <div class="tmc__blob tmc__blob--green" aria-hidden="true" />
    <div class="tmc__blob tmc__blob--purple" aria-hidden="true" />

    <div class="tmc__inner">
      <!-- Header -->
      <div class="tmc__header">
        <div class="tmc__header-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </div>
        <span class="tmc__eyebrow">Prediction Verified</span>
      </div>

      <!-- Content rows -->
      <div class="tmc__rows">
        <div class="tmc__row tmc__row--neutral">
          <div class="tmc__row-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#534AB7" stroke-width="2.5">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <p class="tmc__row-text">
            <strong>We predicted</strong><br/>
            {{ productName }} would run out in {{ predictedDays }} days
          </p>
        </div>

        <div class="tmc__row tmc__row--green">
          <div class="tmc__row-icon tmc__row-icon--green">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#52C41A" stroke-width="2.5">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <p class="tmc__row-text">
            <strong class="tmc__row-text--green">It ran out</strong><br/>
            in {{ actualDays === predictedDays ? 'exactly' : 'about' }} {{ actualDays }} days
          </p>
        </div>
      </div>

      <!-- Footer -->
      <div class="tmc__footer">
        <p class="tmc__footer-label">Accuracy improving daily</p>
        <div class="tmc__accuracy">
          <span class="tmc__accuracy-dot" />
          <span class="tmc__accuracy-label">{{ accuracyLabel }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tmc {
  position:      relative;
  border-radius: 24px;
  overflow:      hidden;
  padding:       24px;
  background:    linear-gradient(145deg,
    rgba(83,74,183,0.08) 0%,
    rgba(255,255,255,0.95) 40%,
    rgba(82,196,26,0.04) 100%
  );
  border:        1px solid rgba(83,74,183,0.16);
  box-shadow:    0 8px 30px rgba(0,0,0,0.06);
  transition:    box-shadow 0.3s, transform 0.3s;
}
.tmc:hover {
  box-shadow: 0 12px 36px rgba(0,0,0,0.09);
  transform:  translateY(-1px);
}

.tmc__blob {
  position:       absolute;
  border-radius:  50%;
  pointer-events: none;
  filter:         blur(28px);
}
.tmc__blob--green  { top: -20px; right: -16px; width: 90px; height: 90px; background: rgba(82,196,26,0.12); }
.tmc__blob--purple { bottom: -16px; left: -12px; width: 110px; height: 110px; background: rgba(83,74,183,0.1); }

.tmc__inner { position: relative; }

/* Header */
.tmc__header {
  display:       flex;
  align-items:   center;
  gap:           8px;
  margin-bottom: 18px;
}
.tmc__header-icon {
  width:           30px;
  height:          30px;
  border-radius:   10px;
  background:      linear-gradient(135deg, rgba(82,196,26,0.18), rgba(82,196,26,0.08));
  display:         flex;
  align-items:     center;
  justify-content: center;
  color:           #52C41A;
}
.tmc__eyebrow {
  font-size:      11px;
  font-weight:    700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color:          #534AB7;
}

/* Rows */
.tmc__rows { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }

.tmc__row {
  display:     flex;
  align-items: flex-start;
  gap:         10px;
  padding:     12px 14px;
  border-radius: 14px;
}
.tmc__row--neutral {
  background: rgba(255,255,255,0.6);
  backdrop-filter: blur(4px);
  border: 1px solid rgba(0,0,0,0.05);
}
.tmc__row--green {
  background: linear-gradient(135deg, rgba(82,196,26,0.08), rgba(82,196,26,0.04));
  border: 1px solid rgba(82,196,26,0.2);
}

.tmc__row-icon {
  flex-shrink:     0;
  width:           26px;
  height:          26px;
  border-radius:   8px;
  background:      rgba(83,74,183,0.08);
  display:         flex;
  align-items:     center;
  justify-content: center;
  margin-top:      1px;
}
.tmc__row-icon--green { background: rgba(255,255,255,0.9); box-shadow: 0 1px 4px rgba(0,0,0,0.08); }

.tmc__row-text {
  font-size:   13px;
  color:       #1A1A1A;
  line-height: 1.5;
}
.tmc__row-text strong { font-weight: 700; }
.tmc__row-text--green { color: #52C41A; }

/* Footer */
.tmc__footer {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  padding-top:     16px;
  border-top:      1px solid rgba(83,74,183,0.1);
}
.tmc__footer-label { font-size: 11px; color: rgba(26,26,26,0.5); }
.tmc__accuracy { display: flex; align-items: center; gap: 5px; }
.tmc__accuracy-dot {
  width:         6px;
  height:        6px;
  border-radius: 50%;
  background:    #52C41A;
  animation:     tmc-pulse 1.8s ease-in-out infinite;
}
@keyframes tmc-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
.tmc__accuracy-label { font-size: 11px; font-weight: 700; color: #52C41A; }
</style>