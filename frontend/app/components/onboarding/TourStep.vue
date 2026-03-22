<!-- frontend/app/components/onboarding/TourStep.vue
     A single positioned tooltip that attaches to a real DOM element.
     Renders a spotlight ring around the target, and a tooltip bubble.
-->
<script setup lang="ts">
const props = defineProps<{
  /** CSS selector for the element to spotlight */
  target:   string
  title:    string
  body:     string
  step:     number
  total:    number
  /** 'top' | 'bottom' | 'left' | 'right' — default 'bottom' */
  placement?: 'top' | 'bottom' | 'left' | 'right'
}>()

const emit = defineEmits<{
  next: []
  skip: []
}>()

const placement = computed(() => props.placement ?? 'bottom')

// ── Position computation ──────────────────────────────────────────
const rect    = ref<DOMRect | null>(null)
const winW    = ref(0)
const winH    = ref(0)

const updateRect = () => {
  if (typeof window === 'undefined') return
  const el = document.querySelector(props.target)
  if (!el) return
  rect.value = el.getBoundingClientRect()
  winW.value  = window.innerWidth
  winH.value  = window.innerHeight
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

onMounted(() => {
  updateRect()
  window.addEventListener('resize', updateRect)
  window.addEventListener('scroll', updateRect, true)
})
onUnmounted(() => {
  window.removeEventListener('resize', updateRect)
  window.removeEventListener('scroll', updateRect, true)
})

// Spotlight ring position
const spotStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const pad = 8
  return {
    top:    `${rect.value.top - pad + window.scrollY}px`,
    left:   `${rect.value.left - pad}px`,
    width:  `${rect.value.width + pad * 2}px`,
    height: `${rect.value.height + pad * 2}px`,
  }
})

// Tooltip position
const TIP_W = 280
const tipStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const r = rect.value
  const gap = 14
  const scroll = typeof window !== 'undefined' ? window.scrollY : 0

  if (placement.value === 'bottom') return {
    top:  `${r.bottom + gap + scroll}px`,
    left: `${Math.max(12, Math.min(r.left + r.width / 2 - TIP_W / 2, winW.value - TIP_W - 12))}px`,
  }
  if (placement.value === 'top') return {
    top:  `${r.top - 140 - gap + scroll}px`,
    left: `${Math.max(12, Math.min(r.left + r.width / 2 - TIP_W / 2, winW.value - TIP_W - 12))}px`,
  }
  if (placement.value === 'right') return {
    top:  `${r.top + r.height / 2 - 60 + scroll}px`,
    left: `${r.right + gap}px`,
  }
  // left
  return {
    top:  `${r.top + r.height / 2 - 60 + scroll}px`,
    left: `${Math.max(12, r.left - TIP_W - gap)}px`,
  }
})
</script>

<template>
  <Teleport to="body">
    <!-- Dark overlay with spotlight cutout via box-shadow -->
    <div class="tour-overlay" />

    <!-- Spotlight ring around target -->
    <div class="tour-spot" :style="spotStyle" />

    <!-- Tooltip bubble -->
    <div class="tour-tip" :style="tipStyle">
      <div class="tour-tip__header">
        <span class="tour-tip__step">{{ step }} / {{ total }}</span>
        <button class="tour-tip__skip" @click="emit('skip')">Skip tour</button>
      </div>
      <h3 class="tour-tip__title">{{ title }}</h3>
      <p class="tour-tip__body">{{ body }}</p>
      <div class="tour-tip__footer">
        <div class="tour-tip__dots">
          <span
            v-for="i in total" :key="i"
            class="tour-tip__dot"
            :class="{ 'tour-tip__dot--active': i === step }"
          />
        </div>
        <button class="tour-tip__next" @click="emit('next')">
          {{ step < total ? 'Next →' : 'Done ✓' }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* Semi-transparent overlay */
.tour-overlay {
  position:   fixed;
  inset:      0;
  z-index:    9000;
  background: rgba(0,0,0,0.46);
  pointer-events: none;
}

/* Spotlight ring */
.tour-spot {
  position:      absolute;
  z-index:       9001;
  border-radius: 12px;
  border:        2px solid rgba(83,74,183,0.8);
  box-shadow:    0 0 0 4000px rgba(0,0,0,0.46);
  pointer-events: none;
  animation:     spot-pulse 1.8s ease-in-out infinite;
}
@keyframes spot-pulse {
  0%, 100% { border-color: rgba(83,74,183,0.8); box-shadow: 0 0 0 4000px rgba(0,0,0,0.46), 0 0 0 6px rgba(83,74,183,0.2); }
  50%       { border-color: rgba(83,74,183,1);   box-shadow: 0 0 0 4000px rgba(0,0,0,0.46), 0 0 0 8px rgba(83,74,183,0.12); }
}

/* Tooltip */
.tour-tip {
  position:      absolute;
  z-index:       9002;
  width:         280px;
  background:    #fff;
  border-radius: 18px;
  padding:       20px 20px 16px;
  box-shadow:    0 20px 60px rgba(0,0,0,0.18), 0 4px 16px rgba(83,74,183,0.12);
  border:        1px solid rgba(83,74,183,0.12);
  animation:     tip-in 0.3s cubic-bezier(0.16,1,0.3,1);
}
@keyframes tip-in {
  from { opacity: 0; transform: translateY(8px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.tour-tip__header {
  display:         flex;
  justify-content: space-between;
  align-items:     center;
  margin-bottom:   10px;
}
.tour-tip__step {
  font-size:      10px;
  font-weight:    700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color:          #534AB7;
  background:     rgba(83,74,183,0.08);
  padding:        3px 8px;
  border-radius:  999px;
}
.tour-tip__skip {
  font-size:  11px;
  color:      rgba(26,26,26,0.4);
  background: none;
  border:     none;
  cursor:     pointer;
  transition: color 0.15s;
}
.tour-tip__skip:hover { color: rgba(26,26,26,0.7); }

.tour-tip__title {
  font-size:      16px;
  font-weight:    700;
  color:          #1A1A1A;
  letter-spacing: -0.01em;
  margin-bottom:  6px;
}
.tour-tip__body {
  font-size:   13px;
  color:       rgba(26,26,26,0.65);
  line-height: 1.55;
  margin-bottom: 16px;
}

.tour-tip__footer {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  gap:             12px;
}
.tour-tip__dots { display: flex; gap: 5px; }
.tour-tip__dot {
  width:         6px;
  height:        6px;
  border-radius: 50%;
  background:    #E8E7E3;
  transition:    background 0.2s, width 0.2s;
}
.tour-tip__dot--active { background: #534AB7; width: 16px; border-radius: 3px; }

.tour-tip__next {
  padding:       8px 16px;
  background:    linear-gradient(135deg, #534AB7, #6B62C9);
  color:         #fff;
  border:        none;
  border-radius: 10px;
  font-size:     13px;
  font-weight:   700;
  cursor:        pointer;
  transition:    transform 0.15s, box-shadow 0.15s;
  box-shadow:    0 2px 8px rgba(83,74,183,0.28);
}
.tour-tip__next:hover { transform: scale(1.03); box-shadow: 0 4px 14px rgba(83,74,183,0.38); }
</style>