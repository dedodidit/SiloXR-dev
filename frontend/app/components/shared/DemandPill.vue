<!-- frontend/app/components/shared/DemandPill.vue -->

<script setup lang="ts">
const props = defineProps<{
  direction: string
  size?:     "sm" | "md"
}>()

const config = computed(() => ({
  increasing: { label: "↑ Rising",  class: "demand-pill--increasing" },
  stable:     { label: "→ Stable",  class: "demand-pill--stable"     },
  decreasing: { label: "↓ Easing",  class: "demand-pill--decreasing" },
}[props.direction] ?? { label: props.direction, class: "demand-pill--stable" }))
</script>

<template>
  <span class="demand-pill" :class="config.class">
    {{ config.label }}
  </span>
</template>