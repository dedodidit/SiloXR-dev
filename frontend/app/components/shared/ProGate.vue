<!-- frontend/app/components/shared/ProGate.vue -->

<script setup lang="ts">
defineProps<{ feature: string }>()
</script>

<template>
  <div class="pro-gate surface">
    <div class="pro-gate__icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
          stroke="var(--color-amber)" stroke-width="1.5" stroke-linejoin="round"/>
      </svg>
    </div>
    <p class="pro-gate__title">{{ feature }} is a Pro feature</p>
    <p class="pro-gate__sub">
      Upgrade to SiloXR Pro to access predictions, decisions, and alerts.
    </p>
    <NuxtLink to="/billing/upgrade" class="pro-gate__btn">
      Upgrade to Pro
    </NuxtLink>
  </div>
</template>

<style scoped>
.pro-gate {
  padding:        40px 32px;
  text-align:     center;
  display:        flex;
  flex-direction: column;
  align-items:    center;
  gap:            12px;
}
.pro-gate__icon  { margin-bottom: 4px; }
.pro-gate__title { font-size: 15px; font-weight: 600; color: var(--color-text); }
.pro-gate__sub   { font-size: 13px; color: var(--color-text-muted); max-width: 300px; }
.pro-gate__btn {
  margin-top:    8px;
  padding:       10px 24px;
  background:    var(--color-purple);
  color:         #fff;
  border-radius: var(--radius-md);
  font-size:     13px;
  font-weight:   600;
  transition:    opacity 0.15s;
}
.pro-gate__btn:hover { opacity: 0.88; }
</style>