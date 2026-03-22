<!-- frontend/app/components/shared/SectionHeader.vue -->

<script setup lang="ts">
defineProps<{
  title:    string
  count?:   number
  countBg?: string
  countColor?: string
  hint?:    string
}>()
</script>

<template>
  <div class="section-header">
    <div class="section-header__left">
      <h2 class="section-header__title">{{ title }}</h2>
      <span
        v-if="count != null"
        class="section-header__count"
        :style="{
          background: countBg   ?? 'var(--purple-bg)',
          color:      countColor ?? 'var(--purple)',
        }"
      >
        {{ count }}
      </span>
    </div>
    <span v-if="hint" class="t-hint">{{ hint }}</span>
    <slot name="right" />
  </div>
</template>