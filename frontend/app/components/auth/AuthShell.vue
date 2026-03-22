<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../../constants/site"

defineProps<{
  eyebrow: string
  title: string
  subtitle: string
  panelTitle?: string
  panelCopy?: string
}>()
</script>

<template>
  <div class="auth-shell">
    <div class="auth-shell__backdrop" />
    <div class="auth-shell__grid">
      <aside class="auth-shell__panel">
        <div class="auth-shell__brand">
          <div class="auth-shell__brand-mark" aria-hidden="true">
            <svg viewBox="0 0 12 12" fill="none" width="14" height="14">
              <path d="M2 9L6 3L10 9H2Z" fill="white" opacity="0.95" />
              <path d="M4 9L6 6L8 9H4Z" fill="white" opacity="0.5" />
            </svg>
          </div>
          <div>
            <p class="auth-shell__brand-name">SiloXR</p>
            <p class="auth-shell__brand-sub">Decision Engine</p>
          </div>
        </div>

        <div class="auth-shell__story">
          <p class="auth-shell__eyebrow">{{ panelTitle || "Decision operating system" }}</p>
          <h2 class="auth-shell__story-title">{{ title }}</h2>
          <p class="auth-shell__story-copy">
            {{ panelCopy || "Move from uncertainty to clear action with one consistent workflow." }}
          </p>
        </div>

        <div class="auth-shell__chips">
          <span class="auth-shell__chip">Baseline-aware</span>
          <span class="auth-shell__chip">Decision-first</span>
          <span class="auth-shell__chip">Offline-ready</span>
        </div>

        <p class="auth-shell__contact">
          Contact:
          <a :href="SITE_CONTACT_MAILTO" class="auth-shell__contact-link">{{ SITE_CONTACT_EMAIL }}</a>
        </p>
      </aside>

      <section class="auth-shell__card surface">
        <div class="auth-shell__card-head">
          <p class="auth-shell__form-eyebrow">{{ eyebrow }}</p>
          <h1 class="auth-shell__form-title">{{ title }}</h1>
          <p class="auth-shell__form-sub">{{ subtitle }}</p>
        </div>

        <slot />
      </section>
    </div>
  </div>
</template>

<style scoped>
.auth-shell {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--purple) 18%, transparent), transparent 38%),
    radial-gradient(circle at bottom right, color-mix(in srgb, var(--icon-accent) 14%, transparent), transparent 34%),
    linear-gradient(145deg, var(--bg) 0%, color-mix(in srgb, var(--purple) 8%, var(--bg)) 100%);
}
.auth-shell__backdrop {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.18), transparent 38%),
    linear-gradient(315deg, rgba(0,0,0,0.04), transparent 40%);
}
.auth-shell__grid {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: minmax(320px, 0.92fr) minmax(360px, 0.88fr);
  gap: 24px;
  align-items: stretch;
}
.auth-shell__panel {
  padding: 28px;
  border-radius: 28px;
  color: #fff;
  background:
    radial-gradient(circle at top right, rgba(255,255,255,0.14), transparent 28%),
    linear-gradient(145deg, #1B1741 0%, #2F2871 55%, #534AB7 100%);
  box-shadow: 0 28px 70px rgba(22, 17, 62, 0.34);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28px;
}
:root[data-theme="dark"] .auth-shell__panel {
  background:
    radial-gradient(circle at top right, rgba(255,255,255,0.08), transparent 30%),
    linear-gradient(145deg, #121223 0%, #1C1B3D 54%, #2D2770 100%);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.48);
}
.auth-shell__brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.auth-shell__brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.18);
}
.auth-shell__brand-name {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
}
.auth-shell__brand-sub {
  font-size: 11px;
  color: rgba(255,255,255,0.72);
}
.auth-shell__eyebrow,
.auth-shell__form-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.auth-shell__eyebrow {
  color: rgba(255,255,255,0.72);
}
.auth-shell__story-title {
  margin-top: 10px;
  font-size: clamp(32px, 4vw, 44px);
  line-height: 1.04;
  letter-spacing: -0.04em;
}
.auth-shell__story-copy {
  margin-top: 12px;
  max-width: 34ch;
  font-size: 15px;
  line-height: 1.7;
  color: rgba(255,255,255,0.78);
}
.auth-shell__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.auth-shell__chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.12);
  font-size: 12px;
  font-weight: 600;
}
.auth-shell__contact {
  font-size: 12px;
  color: rgba(255,255,255,0.82);
}
.auth-shell__contact-link {
  color: #fff;
  font-weight: 700;
  text-decoration: none;
}
.auth-shell__contact-link:hover {
  text-decoration: underline;
}
.auth-shell__card {
  padding: 34px 32px;
  border-radius: 28px;
  box-shadow: 0 24px 60px rgba(83,74,183,0.12), 0 4px 16px rgba(0,0,0,0.05);
}
:root[data-theme="dark"] .auth-shell__card {
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--purple-bg) 28%, transparent), transparent 28%),
    var(--bg-card);
  border-color: color-mix(in srgb, var(--border-strong) 88%, transparent);
  box-shadow: 0 26px 72px rgba(0,0,0,0.42), 0 8px 20px rgba(0,0,0,0.22);
}
.auth-shell__card-head {
  margin-bottom: 20px;
}
.auth-shell__form-eyebrow {
  color: var(--text-3);
}
.auth-shell__form-title {
  margin-top: 8px;
  font-size: 30px;
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: var(--text);
}
.auth-shell__form-sub {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-2);
}
@media (max-width: 940px) {
  .auth-shell__grid {
    grid-template-columns: 1fr;
  }
  .auth-shell__panel {
    min-height: 240px;
  }
}
@media (max-width: 640px) {
  .auth-shell {
    padding: 18px;
  }
  .auth-shell__panel,
  .auth-shell__card {
    padding: 24px 20px;
    border-radius: 22px;
  }
  .auth-shell__story-title,
  .auth-shell__form-title {
    font-size: 28px;
  }
}
</style>
