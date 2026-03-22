<script setup lang="ts">
const props = defineProps<{
  score: number
  label?: string
  size?: "sm" | "md"
}>()

const pct = computed(() => Math.round(props.score * 100))
const tone = computed(() => {
  if (props.score >= 0.75) return { label: "HIGH", color: "#3B6D11", bg: "#EAF3DE", fill: "linear-gradient(90deg, #78B13F 0%, #3B6D11 100%)" }
  if (props.score >= 0.45) return { label: "MEDIUM", color: "#854F0B", bg: "#FAEEDA", fill: "linear-gradient(90deg, #F4C65D 0%, #C37A10 100%)" }
  return { label: "LOW", color: "#A32D2D", bg: "#FCEBEB", fill: "linear-gradient(90deg, #F28C8C 0%, #A32D2D 100%)" }
})
</script>

<template>
  <span class="conf-badge" :class="`conf-badge--${size ?? 'md'}`" :style="{ background: tone.bg, color: tone.color }">
    <span class="conf-badge__meta">
      <strong>{{ tone.label }}</strong>
      <span>{{ label ?? `${pct}% confidence` }}</span>
    </span>
    <span class="conf-badge__bar">
      <span class="conf-badge__fill" :style="{ width: `${pct}%`, background: tone.fill }" />
    </span>
  </span>
</template>

<style scoped>
.conf-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 6px 10px;
  min-width: 132px;
}
.conf-badge--sm { min-width: 118px; padding: 5px 8px; }
.conf-badge__meta { display: flex; flex-direction: column; line-height: 1.1; }
.conf-badge__meta strong { font-size: 10px; letter-spacing: .06em; }
.conf-badge__meta span { font-size: 10px; opacity: .9; }
.conf-badge__bar { width: 44px; height: 6px; border-radius: 999px; background: rgba(20,20,18,.10); overflow: hidden; }
.conf-badge__fill { display: block; height: 100%; border-radius: inherit; }
</style>
