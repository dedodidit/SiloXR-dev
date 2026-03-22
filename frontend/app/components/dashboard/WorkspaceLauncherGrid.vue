<script setup lang="ts">
import { workspaceSections } from "../../constants/workspaceSections"

defineProps<{
  title?: string
  hint?: string
}>()
</script>

<template>
  <section class="wlg surface">
    <div class="wlg__head">
      <div>
        <p class="wlg__eyebrow">Focused views</p>
        <h3 class="wlg__title">{{ title || "Open a workspace" }}</h3>
        <p class="wlg__hint">{{ hint || "Move from the main dashboard into a cleaner view for each decision surface." }}</p>
      </div>
    </div>

    <div class="wlg__grid">
      <NuxtLink
        v-for="section in workspaceSections"
        :key="section.slug"
        class="wlg__card"
        :to="`/workspace/${section.slug}`"
      >
        <span class="wlg__icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path :d="section.icon" />
          </svg>
        </span>
        <div class="wlg__copy">
          <span class="wlg__name">{{ section.title }}</span>
          <span class="wlg__desc">{{ section.description }}</span>
        </div>
      </NuxtLink>
    </div>
  </section>
</template>

<style scoped>
.wlg {
  padding: 8px 0 4px;
  border: 0;
  background: transparent;
  box-shadow: none;
  animation: wlg-fade-up .55s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.wlg__head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 20px;
  padding: 0 4px;
  animation: wlg-fade-up .55s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: .04s;
}
.wlg__eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.wlg__title {
  margin-top: 4px;
  font-size: 20px;
  line-height: 1.2;
  color: var(--text);
}
.wlg__hint {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-3);
}
.wlg__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 18px;
  justify-content: center;
  align-items: stretch;
}
.wlg__card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: center;
  text-align: center;
  min-height: 156px;
  padding: 22px 20px;
  border-radius: 22px;
  border: 1px solid var(--border-subtle);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 86%, transparent)),
    radial-gradient(circle at top right, rgba(83,74,183,0.08), transparent 38%);
  text-decoration: none;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  position: relative;
  transition: transform .28s cubic-bezier(0.16, 1, 0.3, 1), box-shadow .28s cubic-bezier(0.16, 1, 0.3, 1), border-color .22s ease, background .22s ease;
  animation: wlg-card-in .6s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.wlg__card:hover {
  transform: translateY(-3px);
  border-color: rgba(83,74,183,0.18);
  box-shadow: var(--shadow-hover);
}
.wlg__card::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 20%, color-mix(in srgb, var(--bg-card) 55%, white 45%) 50%, transparent 80%);
  transform: translateX(-130%);
  transition: transform .65s cubic-bezier(0.16, 1, 0.3, 1);
  pointer-events: none;
}
.wlg__card:hover::after {
  transform: translateX(130%);
}
.wlg__icon {
  display: inline-flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(83,74,183,0.12), rgba(83,74,183,0.04));
  color: var(--icon-accent);
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--bg-card) 78%, white 22%);
  transition: transform .28s cubic-bezier(0.16, 1, 0.3, 1), background .28s ease;
}
.wlg__card:hover .wlg__icon {
  transform: translateY(-2px) scale(1.03);
  background: linear-gradient(135deg, rgba(83,74,183,0.16), rgba(83,74,183,0.06));
}
.wlg__copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}
.wlg__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
}
.wlg__desc {
  max-width: 24ch;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-3);
}
.wlg__card:nth-child(1) { animation-delay: .06s; }
.wlg__card:nth-child(2) { animation-delay: .1s; }
.wlg__card:nth-child(3) { animation-delay: .14s; }
.wlg__card:nth-child(4) { animation-delay: .18s; }
.wlg__card:nth-child(5) { animation-delay: .22s; }
.wlg__card:nth-child(6) { animation-delay: .26s; }
.wlg__card:nth-child(7) { animation-delay: .3s; }
.wlg__card:nth-child(8) { animation-delay: .34s; }
.wlg__card:nth-child(9) { animation-delay: .38s; }
.wlg__card:nth-child(10) { animation-delay: .42s; }

@keyframes wlg-fade-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes wlg-card-in {
  from {
    opacity: 0;
    transform: translateY(16px) scale(.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
