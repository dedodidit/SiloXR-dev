<!-- frontend/app/components/onboarding/TourStep.vue -->
<script setup lang="ts">
const props = defineProps<{
  target: string
  title: string
  body: string
  step: number
  total: number
  placement?: "top" | "bottom" | "left" | "right"
}>()

const emit = defineEmits<{
  next: []
  skip: []
}>()

const placement = computed(() => props.placement ?? "bottom")
const isMobile = ref(false)
const rect = ref<DOMRect | null>(null)
const winW = ref(0)

const updateRect = () => {
  if (typeof window === "undefined") return

  isMobile.value = window.innerWidth <= 768
  winW.value = window.innerWidth

  const el = document.querySelector(props.target)
  if (!el) {
    rect.value = null
    return
  }

  rect.value = el.getBoundingClientRect()
  el.scrollIntoView({
    behavior: "smooth",
    block: isMobile.value ? "center" : "nearest",
    inline: "nearest",
  })
}

onMounted(() => {
  updateRect()
  window.addEventListener("resize", updateRect)
  window.addEventListener("scroll", updateRect, true)
})

onUnmounted(() => {
  window.removeEventListener("resize", updateRect)
  window.removeEventListener("scroll", updateRect, true)
})

const spotStyle = computed(() => {
  if (!rect.value || isMobile.value) return { display: "none" }
  const pad = 8
  return {
    top: `${rect.value.top - pad + window.scrollY}px`,
    left: `${rect.value.left - pad}px`,
    width: `${rect.value.width + pad * 2}px`,
    height: `${rect.value.height + pad * 2}px`,
  }
})

const TIP_W = 300
const tipStyle = computed(() => {
  if (isMobile.value) {
    return {
      left: "16px",
      right: "16px",
      bottom: "16px",
      top: "auto",
      width: "auto",
    }
  }

  if (!rect.value) {
    return {
      top: "24px",
      left: `${Math.max(12, (winW.value - TIP_W) / 2)}px`,
    }
  }

  const r = rect.value
  const gap = 14
  const scroll = typeof window !== "undefined" ? window.scrollY : 0

  if (placement.value === "bottom") {
    return {
      top: `${r.bottom + gap + scroll}px`,
      left: `${Math.max(12, Math.min(r.left + r.width / 2 - TIP_W / 2, winW.value - TIP_W - 12))}px`,
    }
  }

  if (placement.value === "top") {
    return {
      top: `${Math.max(12, r.top - 150 - gap + scroll)}px`,
      left: `${Math.max(12, Math.min(r.left + r.width / 2 - TIP_W / 2, winW.value - TIP_W - 12))}px`,
    }
  }

  if (placement.value === "right") {
    return {
      top: `${r.top + r.height / 2 - 70 + scroll}px`,
      left: `${Math.min(r.right + gap, winW.value - TIP_W - 12)}px`,
    }
  }

  return {
    top: `${r.top + r.height / 2 - 70 + scroll}px`,
    left: `${Math.max(12, r.left - TIP_W - gap)}px`,
  }
})
</script>

<template>
  <Teleport to="body">
    <div class="tour-overlay" />
    <div class="tour-spot" :style="spotStyle" />

    <div class="tour-tip" :class="{ 'tour-tip--mobile': isMobile }" :style="tipStyle">
      <div class="tour-tip__header">
        <span class="tour-tip__step">{{ step }} / {{ total }}</span>
        <button class="tour-tip__skip" @click="emit('skip')">Skip tour</button>
      </div>
      <h3 class="tour-tip__title">{{ title }}</h3>
      <p class="tour-tip__body">{{ body }}</p>
      <div class="tour-tip__footer">
        <div class="tour-tip__dots">
          <span
            v-for="i in total"
            :key="i"
            class="tour-tip__dot"
            :class="{ 'tour-tip__dot--active': i === step }"
          />
        </div>
        <button class="tour-tip__next" @click="emit('next')">
          {{ step < total ? "Next" : "Done" }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.tour-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  background: rgba(0, 0, 0, 0.46);
  pointer-events: none;
}

.tour-spot {
  position: absolute;
  z-index: 9001;
  border-radius: 12px;
  border: 2px solid rgba(83, 74, 183, 0.8);
  box-shadow: 0 0 0 4000px rgba(0, 0, 0, 0.46);
  pointer-events: none;
  animation: spot-pulse 1.8s ease-in-out infinite;
}

@keyframes spot-pulse {
  0%, 100% {
    border-color: rgba(83, 74, 183, 0.8);
    box-shadow: 0 0 0 4000px rgba(0, 0, 0, 0.46), 0 0 0 6px rgba(83, 74, 183, 0.2);
  }
  50% {
    border-color: rgba(83, 74, 183, 1);
    box-shadow: 0 0 0 4000px rgba(0, 0, 0, 0.46), 0 0 0 8px rgba(83, 74, 183, 0.12);
  }
}

.tour-tip {
  position: absolute;
  z-index: 9002;
  width: 300px;
  background: #fff;
  border-radius: 18px;
  padding: 20px 20px 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.18), 0 4px 16px rgba(83, 74, 183, 0.12);
  border: 1px solid rgba(83, 74, 183, 0.12);
  animation: tip-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.tour-tip--mobile {
  position: fixed;
  border-radius: 22px;
  padding: 18px 18px 14px;
  max-height: min(52vh, 420px);
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
}

@keyframes tip-in {
  from { opacity: 0; transform: translateY(8px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.tour-tip__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.tour-tip__step {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #534ab7;
  background: rgba(83, 74, 183, 0.08);
  padding: 3px 8px;
  border-radius: 999px;
}

.tour-tip__skip {
  font-size: 11px;
  color: rgba(26, 26, 26, 0.45);
  background: none;
  border: none;
  cursor: pointer;
}

.tour-tip__title {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -0.01em;
  margin-bottom: 6px;
}

.tour-tip__body {
  font-size: 13px;
  color: rgba(26, 26, 26, 0.68);
  line-height: 1.6;
  margin-bottom: 16px;
}

.tour-tip__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tour-tip__dots {
  display: flex;
  gap: 5px;
}

.tour-tip__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e8e7e3;
  transition: background 0.2s, width 0.2s;
}

.tour-tip__dot--active {
  background: #534ab7;
  width: 16px;
  border-radius: 3px;
}

.tour-tip__next {
  padding: 8px 16px;
  background: linear-gradient(135deg, #534ab7, #6b62c9);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(83, 74, 183, 0.28);
}

.tour-tip__next:hover {
  transform: scale(1.03);
  box-shadow: 0 4px 14px rgba(83, 74, 183, 0.38);
}

@media (max-width: 768px) {
  .tour-tip__footer {
    flex-direction: column;
    align-items: stretch;
  }

  .tour-tip__dots {
    justify-content: center;
  }

  .tour-tip__next {
    width: 100%;
  }
}
</style>
