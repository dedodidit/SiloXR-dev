<!-- frontend/app/components/dashboard/NextActionsList.vue
     Translated from Figma NextActionsList.tsx.
     Receives the top priority decisions from the store and renders
     them as a ranked urgency list with impact figures.
-->
<script setup lang="ts">
const props = defineProps<{
  items: Array<{
    id:           string
    product_name: string
    product_sku:  string
    action:       string
    severity:     string
    estimated_revenue_loss?: number
    days_remaining_at_decision?: number | null
  }>
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const ACTION_LABEL: Record<string, string> = {
  ALERT_CRITICAL: 'Restock urgently',
  ALERT_LOW:      'Prepare restock',
  REORDER:        'Place reorder',
  CHECK_STOCK:    'Verify count',
  MONITOR:        'Monitor',
  HOLD:           'No action',
}

const urgencyOf = (severity: string) => {
  if (severity === 'critical') return 'high'
  if (severity === 'warning')  return 'medium'
  return 'low'
}

const styles = (urgency: string) => ({
  high: {
    bg:        'nal-item--high',
    textClass: 'nal-item__action--red',
    barClass:  'nal-item__bar--red',
    numClass:  'nal-item__num--red',
  },
  medium: {
    bg:        'nal-item--medium',
    textClass: 'nal-item__action--amber',
    barClass:  'nal-item__bar--amber',
    numClass:  'nal-item__num--amber',
  },
  low: {
    bg:        'nal-item--low',
    textClass: 'nal-item__action--green',
    barClass:  'nal-item__bar--green',
    numClass:  'nal-item__num--green',
  },
}[urgency] ?? {
  bg: 'nal-item--low', textClass: 'nal-item__action--green',
  barClass: 'nal-item__bar--green', numClass: 'nal-item__num--green',
})

const timeframeOf = (days: number | null | undefined) => {
  if (days == null) return 'Review soon'
  if (days <= 1)    return `~${Math.max(1, Math.round(days * 24))} hrs`
  return `~${Math.round(days)} days`
}
</script>

<template>
  <div class="nal">
    <div class="nal__head">
      <div>
        <h2 class="nal__title">Next Actions</h2>
        <p class="nal__sub">Prioritised by impact and urgency</p>
      </div>
      <div class="nal__count" v-if="items.length">
        {{ items.length }} pending
      </div>
    </div>

    <div class="nal__list">
      <button
        v-for="(item, idx) in items"
        :key="item.id"
        type="button"
        class="nal-item"
        :class="styles(urgencyOf(item.severity)).bg"
        @click="emit('select', item.id)"
      >
        <!-- Hover shimmer -->
        <div class="nal-item__shimmer" aria-hidden="true" />

        <!-- Priority bar + number -->
        <div class="nal-item__priority">
          <div class="nal-item__bar" :class="styles(urgencyOf(item.severity)).barClass" />
          <div class="nal-item__num" :class="styles(urgencyOf(item.severity)).numClass">
            {{ idx + 1 }}
          </div>
        </div>

        <!-- Content -->
        <div class="nal-item__content">
          <div class="nal-item__top-row">
            <span class="nal-item__name">{{ item.product_name }}</span>
            <span class="nal-item__dot" :class="styles(urgencyOf(item.severity)).barClass" />
            <span class="nal-item__action" :class="styles(urgencyOf(item.severity)).textClass">
              {{ ACTION_LABEL[item.action] ?? item.action }}
            </span>
          </div>
          <div class="nal-item__meta">
            <span class="nal-item__meta-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
              </svg>
              {{ timeframeOf(item.days_remaining_at_decision) }}
            </span>
            <span v-if="(item.estimated_revenue_loss ?? 0) > 0" class="nal-item__meta-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                <polyline points="17 6 23 6 23 12"/>
              </svg>
              <strong>₦{{ Math.round(item.estimated_revenue_loss ?? 0).toLocaleString() }}</strong>
              at risk
            </span>
          </div>
        </div>

        <!-- Arrow -->
        <div class="nal-item__arrow" :class="styles(urgencyOf(item.severity)).textClass">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
          </svg>
        </div>
      </button>

      <!-- Empty state -->
      <div v-if="!items.length" class="nal__empty">
        <p>No pending actions — all products are stable.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nal {
  background:    #fff;
  border-radius: 24px;
  padding:       28px 28px 24px;
  box-shadow:    0 8px 30px rgba(0,0,0,0.06);
  border:        1px solid rgba(0,0,0,0.04);
}

.nal__head {
  display:         flex;
  align-items:     flex-start;
  justify-content: space-between;
  gap:             12px;
  margin-bottom:   20px;
}
.nal__title {
  font-size:      22px;
  font-weight:    800;
  letter-spacing: -0.02em;
  color:          #1A1A1A;
}
.nal__sub {
  font-size:  13px;
  color:      rgba(26,26,26,0.5);
  margin-top: 3px;
}
.nal__count {
  padding:       6px 14px;
  background:    rgba(83,74,183,0.08);
  border-radius: 999px;
  font-size:     13px;
  font-weight:   700;
  color:         #534AB7;
  white-space:   nowrap;
}

.nal__list { display: flex; flex-direction: column; gap: 10px; }

/* Item */
.nal-item {
  position:      relative;
  display:       flex;
  align-items:   center;
  gap:           14px;
  padding:       16px 18px;
  border-radius: 16px;
  text-align:    left;
  cursor:        pointer;
  border:        1px solid transparent;
  overflow:      hidden;
  transition:    box-shadow 0.25s, transform 0.25s;
  width:         100%;
}
.nal-item:hover {
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
  transform:  translateX(2px);
}

.nal-item--high   { background: linear-gradient(135deg, rgba(255,77,79,0.08) 0%, rgba(255,77,79,0.04) 100%); border-color: rgba(255,77,79,0.18); }
.nal-item--medium { background: linear-gradient(135deg, rgba(250,173,20,0.08) 0%, rgba(250,173,20,0.04) 100%); border-color: rgba(250,173,20,0.18); }
.nal-item--low    { background: linear-gradient(135deg, rgba(82,196,26,0.08) 0%, rgba(82,196,26,0.04) 100%); border-color: rgba(82,196,26,0.18); }

/* Shimmer on hover */
.nal-item__shimmer {
  position:   absolute;
  inset:      0;
  background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.5) 50%, rgba(255,255,255,0) 100%);
  transform:  translateX(-100%);
  transition: transform 0s;
  pointer-events: none;
}
.nal-item:hover .nal-item__shimmer { transform: translateX(100%); transition: transform 0.6s ease; }

/* Priority */
.nal-item__priority { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.nal-item__bar {
  width:         5px;
  height:        44px;
  border-radius: 999px;
  flex-shrink:   0;
  box-shadow:    0 2px 8px rgba(0,0,0,0.12);
}
.nal-item__bar--red   { background: linear-gradient(180deg, #FF4D4F, rgba(255,77,79,0.6)); }
.nal-item__bar--amber { background: linear-gradient(180deg, #FAAD14, rgba(250,173,20,0.6)); }
.nal-item__bar--green { background: linear-gradient(180deg, #52C41A, rgba(82,196,26,0.6)); }

.nal-item__num {
  width:           30px;
  height:          30px;
  border-radius:   50%;
  background:      #fff;
  display:         flex;
  align-items:     center;
  justify-content: center;
  font-size:       13px;
  font-weight:     800;
  box-shadow:      0 1px 4px rgba(0,0,0,0.1);
}
.nal-item__num--red   { color: #FF4D4F; }
.nal-item__num--amber { color: #FAAD14; }
.nal-item__num--green { color: #52C41A; }

/* Content */
.nal-item__content { flex: 1; min-width: 0; }
.nal-item__top-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.nal-item__name    { font-size: 16px; font-weight: 700; color: #1A1A1A; }
.nal-item__dot {
  width: 4px; height: 4px; border-radius: 50%;
}
.nal-item__action  { font-size: 13px; font-weight: 600; }
.nal-item__action--red   { color: #FF4D4F; }
.nal-item__action--amber { color: #FAAD14; }
.nal-item__action--green { color: #52C41A; }

.nal-item__meta { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.nal-item__meta-item {
  display:     flex;
  align-items: center;
  gap:         5px;
  font-size:   12px;
  color:       rgba(26,26,26,0.55);
}
.nal-item__meta-item svg { flex-shrink: 0; }

/* Arrow */
.nal-item__arrow {
  flex-shrink: 0;
  padding:     10px;
  border-radius: 12px;
  background:  rgba(255,255,255,0.7);
  border:      1px solid rgba(0,0,0,0.06);
  transition:  transform 0.2s;
}
.nal-item:hover .nal-item__arrow { transform: translateX(3px); }

/* Empty */
.nal__empty {
  padding:    24px;
  text-align: center;
  font-size:  14px;
  color:      rgba(26,26,26,0.4);
}
</style>