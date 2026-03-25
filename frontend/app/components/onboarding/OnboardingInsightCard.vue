<script setup lang="ts">
defineProps<{
  eyebrow?: string
  headline: string
  detail: string
  note: string
  highlights?: string[]
}>()
</script>

<template>
  <section class="insight-card">
    <p class="insight-card__eyebrow">{{ eyebrow || "Setup complete" }}</p>
    <h3 class="insight-card__headline">{{ headline }}</h3>
    <p class="insight-card__detail">{{ detail }}</p>
    <ul v-if="highlights?.length" class="insight-card__list">
      <li v-for="item in highlights" :key="item">{{ item }}</li>
    </ul>
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
.insight-card__detail,
.insight-card__note {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-2);
}
.insight-card__list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  color: var(--text);
  font-size: 14px;
  line-height: 1.55;
}
.insight-card__note {
  color: var(--text-3);
}
</style>
