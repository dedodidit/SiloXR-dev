<script setup lang="ts">
defineProps<{
  headline: string
  amount: string
  detail: string
  note: string
}>()
</script>

<template>
  <section class="insight-card">
    <p class="insight-card__eyebrow">Immediate insight</p>
    <h3 class="insight-card__headline">{{ headline }}</h3>
    <div class="insight-card__amount">{{ amount }}</div>
    <p class="insight-card__detail">{{ detail }}</p>
    <p class="insight-card__note">{{ note }}</p>
  </section>
</template>

<style scoped>
.insight-card {
  display: grid;
  gap: 10px;
  padding: 22px;
  border-radius: 24px;
  border: 1px solid color-mix(in srgb, #2D7BD0 20%, var(--border-subtle));
  background:
    radial-gradient(circle at top right, color-mix(in srgb, #4AA3FF 16%, transparent), transparent 38%),
    linear-gradient(145deg, color-mix(in srgb, #185FA5 16%, var(--bg-card)), color-mix(in srgb, var(--bg-card) 96%, transparent));
  box-shadow: 0 20px 34px color-mix(in srgb, #185FA5 12%, transparent);
}
.insight-card__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: color-mix(in srgb, #185FA5 76%, var(--text-2));
}
.insight-card__headline {
  margin: 0;
  font-size: 22px;
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: var(--text);
}
.insight-card__amount {
  font-size: clamp(28px, 5vw, 42px);
  font-weight: 900;
  letter-spacing: -0.05em;
  color: #185FA5;
}
.insight-card__detail,
.insight-card__note {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-2);
}
.insight-card__note {
  color: var(--text-3);
}
</style>
