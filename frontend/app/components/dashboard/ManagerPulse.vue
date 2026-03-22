<!-- frontend/app/components/dashboard/ManagerPulse.vue
     Manager Pulse — split into 3 clickable, expandable cards:
       1. Revenue Risk
       2. Verification Debt
       3. Decision Follow-through
     Props driven by dashboard summary data.
-->
<script setup lang="ts">
const props = defineProps<{
  headline?:          string
  subtext?:           string
  revenueAtRisk?:     number
  staleProducts?:     number
  totalProducts?:     number
  criticalAlerts?:    number
  signals?:           Array<{
    key:            string
    title:          string
    value:          string
    tone:           'critical' | 'warning' | 'safe'
    summary:        string
    recommendation: string
    target:         'decisions' | 'stockouts' | 'products' | 'decisions_queue'
  }>
  collapsed?:         boolean
}>()

const emit = defineEmits<{ navigate: [target: string] }>()

const open = ref(!props.collapsed)

// ── Three fixed cards ─────────────────────────────────────────────
const cards = computed(() => {
  const rev  = props.revenueAtRisk   ?? 0
  const stale = props.staleProducts  ?? 0
  const total = props.totalProducts  ?? 1
  const crit  = props.criticalAlerts ?? 0

  return [
    {
      key:    'revenue',
      icon:   'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      title:  'Revenue at Risk',
      value:  rev > 0 ? `₦${rev.toLocaleString()}` : 'All clear',
      sub:    'potential revenue loss this week',
      tone:   rev > 50000 ? 'critical' : rev > 10000 ? 'warning' : 'safe',
      detail: rev > 0
        ? `Based on current stock levels and decision queue, approximately ₦${rev.toLocaleString()} in sales may be at risk. Act on the critical alerts to reduce this.`
        : 'No significant revenue risk detected across your active products.',
      action: { label: 'Review alerts', target: 'decisions' },
    },
    {
      key:    'verification',
      icon:   'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
      title:  'Verification Debt',
      value:  `${stale} / ${total}`,
      sub:    'products need a stock count',
      tone:   stale / Math.max(total, 1) > 0.4 ? 'critical' : stale > 0 ? 'warning' : 'safe',
      detail: stale > 0
        ? `${stale} of your ${total} products have not been physically counted recently. Unverified products produce weaker predictions. A quick count restores accuracy.`
        : 'All products have recent stock verification. Confidence is high.',
      action: { label: 'View products', target: 'products' },
    },
    {
      key:    'followthrough',
      icon:   'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      title:  'Decision Follow-through',
      value:  crit > 0 ? `${crit} pending` : 'On track',
      sub:    crit > 0 ? 'critical decisions need action' : 'no open critical decisions',
      tone:   crit > 2 ? 'critical' : crit > 0 ? 'warning' : 'safe',
      detail: crit > 0
        ? `${crit} critical decision${crit > 1 ? 's are' : ' is'} waiting for your response. Unactioned decisions accumulate over time and reduce system trust.`
        : 'You\'re keeping up with all system recommendations. This improves forecast accuracy.',
      action: { label: 'Open queue', target: 'decisions_queue' },
    },
  ]
})

const toneColor = (tone: string) => ({
  critical: '#FF4D4F',
  warning:  '#FAAD14',
  safe:     '#52C41A',
}[tone] ?? '#534AB7')

const toneBg = (tone: string) => ({
  critical: 'rgba(255,77,79,0.06)',
  warning:  'rgba(250,173,20,0.06)',
  safe:     'rgba(82,196,26,0.06)',
}[tone] ?? 'rgba(83,74,183,0.06)')

// Per-card expanded state
const expanded = ref<Record<string, boolean>>({})
const toggle   = (key: string) => { expanded.value[key] = !expanded.value[key] }
</script>

<template>
  <section class="mp" id="manager-pulse" data-section>

    <!-- Collapsible header -->
    <div class="mp__header" @click="open = !open">
      <div class="mp__header-left">
        <div class="mp__header-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#534AB7"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </svg>
        </div>
        <div>
          <h2 class="mp__title">Manager Pulse</h2>
          <p class="mp__sub">{{ headline ?? 'Revenue risk · verification · follow-through' }}</p>
        </div>
      </div>
      <svg
        width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="rgba(26,26,26,0.4)" stroke-width="2.5"
        class="mp__chevron"
        :style="{ transform: open ? 'rotate(180deg)' : 'rotate(0)' }"
      >
        <path d="M6 9l6 6 6-6"/>
      </svg>
    </div>

    <!-- Cards grid (collapsible) -->
    <Transition name="mp-collapse">
      <div v-if="open" class="mp__grid">
        <div
          v-for="card in cards"
          :key="card.key"
          class="mp-card"
          :style="{ '--tone': toneColor(card.tone), '--tone-bg': toneBg(card.tone) }"
          :class="`mp-card--${card.tone}`"
          @click="toggle(card.key)"
        >
          <!-- Card header -->
          <div class="mp-card__head">
            <div class="mp-card__icon-wrap">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path :d="card.icon"/>
              </svg>
            </div>
            <div class="mp-card__meta">
              <p class="mp-card__title">{{ card.title }}</p>
              <p class="mp-card__val">{{ card.value }}</p>
              <p class="mp-card__sub">{{ card.sub }}</p>
            </div>
            <div
              class="mp-card__tone-chip"
              :style="{ color: toneColor(card.tone), background: toneBg(card.tone) }"
            >
              {{ card.tone }}
            </div>
          </div>

          <!-- Expanded detail -->
          <Transition name="mp-detail">
            <div v-if="expanded[card.key]" class="mp-card__detail">
              <p class="mp-card__detail-text">{{ card.detail }}</p>
              <button
                class="mp-card__action-btn"
                @click.stop="emit('navigate', card.action.target)"
              >
                {{ card.action.label }} →
              </button>
            </div>
          </Transition>

          <!-- Expand indicator -->
          <div class="mp-card__expand-hint">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="rgba(26,26,26,0.3)" stroke-width="2.5"
              :style="{ transform: expanded[card.key] ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .2s' }">
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </div>
        </div>
      </div>
    </Transition>

  </section>
</template>

<style scoped>
.mp { display: flex; flex-direction: column; gap: 12px; }

.mp__header {
  display:      flex;
  align-items:  center;
  justify-content: space-between;
  gap:          12px;
  cursor:       pointer;
  padding:      14px 18px;
  background:   rgba(83,74,183,0.04);
  border-radius: 14px;
  border:       1px solid rgba(83,74,183,0.1);
  transition:   background 0.15s;
  user-select:  none;
}
.mp__header:hover { background: rgba(83,74,183,0.07); }
.mp__header-left  { display: flex; align-items: center; gap: 12px; }
.mp__header-icon  {
  width: 36px; height: 36px; border-radius: 10px;
  background: rgba(83,74,183,0.1);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.mp__title { font-size: 16px; font-weight: 700; color: #1A1A1A; }
.mp__sub   { font-size: 12px; color: rgba(26,26,26,0.5); margin-top: 1px; }
.mp__chevron { flex-shrink: 0; transition: transform 0.25s ease; }

/* Grid */
.mp__grid {
  display:               grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap:                   12px;
}

/* Card */
.mp-card {
  border-radius: 16px;
  padding:       16px;
  background:    var(--tone-bg, rgba(83,74,183,0.05));
  border:        1px solid transparent;
  cursor:        pointer;
  transition:    box-shadow 0.2s, transform 0.2s, border-color 0.2s;
  position:      relative;
  overflow:      hidden;
}
.mp-card--critical { border-color: rgba(255,77,79,0.15); }
.mp-card--warning  { border-color: rgba(250,173,20,0.15); }
.mp-card--safe     { border-color: rgba(82,196,26,0.15);  }
.mp-card:hover {
  transform:  translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.07);
}

.mp-card__head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 4px; }
.mp-card__icon-wrap {
  width:           34px;
  height:          34px;
  border-radius:   10px;
  background:      rgba(255,255,255,0.7);
  border:          1px solid rgba(0,0,0,0.06);
  display:         flex;
  align-items:     center;
  justify-content: center;
  flex-shrink:     0;
  color:           var(--tone, #534AB7);
}
.mp-card__meta { flex: 1; min-width: 0; }
.mp-card__title { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: rgba(26,26,26,0.5); margin-bottom: 3px; }
.mp-card__val   { font-size: 22px; font-weight: 800; color: var(--tone, #1A1A1A); letter-spacing: -0.03em; line-height: 1.1; }
.mp-card__sub   { font-size: 11px; color: rgba(26,26,26,0.5); margin-top: 2px; }
.mp-card__tone-chip {
  flex-shrink:    0;
  padding:        3px 8px;
  border-radius:  999px;
  font-size:      10px;
  font-weight:    700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* Detail */
.mp-card__detail { padding-top: 12px; border-top: 1px solid rgba(0,0,0,0.06); margin-top: 12px; }
.mp-card__detail-text { font-size: 13px; color: rgba(26,26,26,0.65); line-height: 1.6; margin-bottom: 10px; }
.mp-card__action-btn {
  font-size:   12px;
  font-weight: 700;
  color:       var(--tone, #534AB7);
  background:  none;
  border:      none;
  cursor:      pointer;
  padding:     0;
  transition:  opacity 0.15s;
}
.mp-card__action-btn:hover { opacity: 0.7; }

.mp-card__expand-hint { display: flex; justify-content: center; margin-top: 8px; }

/* Transitions */
.mp-collapse-enter-active, .mp-collapse-leave-active { transition: all 0.3s ease; overflow: hidden; }
.mp-collapse-enter-from, .mp-collapse-leave-to { opacity: 0; transform: translateY(-8px); max-height: 0; }
.mp-collapse-enter-to, .mp-collapse-leave-from { max-height: 600px; }

.mp-detail-enter-active, .mp-detail-leave-active { transition: all 0.25s ease; overflow: hidden; }
.mp-detail-enter-from, .mp-detail-leave-to { opacity: 0; max-height: 0; padding-top: 0; margin-top: 0; }
.mp-detail-enter-to, .mp-detail-leave-from { max-height: 200px; }
</style>