<script setup lang="ts">
import type { NotificationRecord, NotificationType } from "../../../types"

const { $api } = useNuxtApp()
const open = ref(false)
const items = ref<NotificationRecord[]>([])
const unreadCount = computed(() => items.value.filter((n) => !n.is_read).length)
const previewItems = computed(() => items.value.slice(0, 5))

const severityColor: Record<string, string> = {
  critical: "var(--severity-critical-text)",
  warning: "var(--severity-warning-text)",
  info: "var(--severity-info-text)",
  ok: "var(--severity-ok-text)",
}

const severityTone: Record<string, string> = {
  critical: "bell-item--critical",
  high: "bell-item--high",
  medium: "bell-item--medium",
  low: "bell-item--low",
}

const channelLabel: Record<string, string> = {
  in_app: "In-app",
  email: "Email",
  whatsapp: "WhatsApp",
}

const typeLabel: Record<NotificationType, string> = {
  stockout_risk: "Stockout risk",
  dead_stock: "Dead stock",
  drop: "Demand drop",
  inactivity_risk: "Inactivity risk",
  generic: "Insight",
}

const load = async () => {
  try {
    items.value = await $api<NotificationRecord[]>("/notifications/")
  } catch {
    // ignore
  }
}

const markRead = async () => {
  await $api("/notifications/read/", { method: "POST" })
  items.value = items.value.map((n) => ({ ...n, is_read: true }))
}

const toggle = async () => {
  open.value = !open.value
  if (open.value) await load()
}

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 2 * 60 * 1000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="bell-wrap">
    <button class="bell-btn" @click="toggle" :aria-label="`${unreadCount} notifications`">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path
          d="M9 2a5 5 0 0 1 5 5v3l1.5 2H2.5L4 10V7a5 5 0 0 1 5-5Z"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
        <path d="M7 14a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.4" />
      </svg>
      <span v-if="unreadCount > 0" class="bell-badge">{{ unreadCount }}</span>
    </button>

    <Transition name="dropdown">
      <div v-if="open" class="bell-dropdown surface">
        <div class="bell-dropdown__header">
          <span>Notifications</span>
          <div class="bell-dropdown__header-actions">
            <button v-if="unreadCount > 0" type="button" class="bell-dropdown__action" @click="markRead">Mark all read</button>
            <button type="button" class="bell-dropdown__close" @click="open = false">x</button>
          </div>
        </div>

        <div class="bell-dropdown__list">
          <div v-if="!previewItems.length" class="bell-dropdown__empty">
            No notifications yet.
          </div>

          <div
            v-for="n in previewItems"
            :key="n.id"
            class="bell-item"
            :class="severityTone[n.severity] ?? 'bell-item--medium'"
            :style="{ borderLeftColor: severityColor[n.severity] ?? 'var(--color-border)' }"
          >
            <div class="bell-item__top">
              <div class="bell-item__title-wrap">
                <p class="bell-item__title">{{ n.title }}</p>
                <span v-if="n.product_name" class="bell-item__product">{{ n.product_name }}</span>
                <span class="bell-item__type">{{ typeLabel[n.notification_type] ?? "Insight" }}</span>
              </div>
              <span class="bell-item__channel">{{ channelLabel[n.channel] ?? "In-app" }}</span>
            </div>
            <p class="bell-item__body">{{ n.body }}</p>
            <p class="bell-item__time">
              {{ new Date(n.created_at).toLocaleString() }}
            </p>
          </div>
        </div>

        <div class="bell-dropdown__footer">
          <NuxtLink to="/notifications" class="bell-dropdown__link" @click="open = false">
            Open notification inbox
          </NuxtLink>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.bell-wrap {
  position: relative;
}
.bell-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  position: relative;
  padding: 6px;
  border-radius: var(--radius-sm);
  transition: color .15s;
}
.bell-btn:hover {
  color: var(--color-text);
}
.bell-badge {
  position: absolute;
  top: 0;
  right: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-red);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bell-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 340px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  max-height: 440px;
  overflow: hidden;
}
.bell-dropdown__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  gap: 10px;
}
.bell-dropdown__header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bell-dropdown__action {
  background: rgba(83, 74, 183, 0.09);
  border: 1px solid rgba(83, 74, 183, 0.14);
  border-radius: 999px;
  color: var(--color-purple);
  font-size: 11px;
  font-weight: 700;
  padding: 5px 9px;
  cursor: pointer;
}
.bell-dropdown__close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: var(--color-text-muted);
  line-height: 1;
}
.bell-dropdown__list {
  overflow-y: auto;
  flex: 1;
}
.bell-dropdown__empty {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-hint);
}
.bell-item {
  padding: 12px 16px;
  border-left: 3px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}
.bell-item--critical {
  background: linear-gradient(90deg, rgba(164, 45, 45, 0.08), transparent 70%);
}
.bell-item--high {
  background: linear-gradient(90deg, rgba(133, 79, 11, 0.08), transparent 70%);
}
.bell-item--medium {
  background: linear-gradient(90deg, rgba(83, 74, 183, 0.08), transparent 70%);
}
.bell-item--low {
  background: linear-gradient(90deg, rgba(59, 109, 17, 0.08), transparent 70%);
}
.bell-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.bell-item__title-wrap {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.bell-item__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.bell-item__product {
  font-size: 11px;
  color: var(--color-text-hint);
}
.bell-item__type {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--color-text-muted);
}
.bell-item__channel {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--color-purple);
  background: var(--color-purple-light, rgba(83, 74, 183, .1));
  padding: 3px 7px;
  border-radius: 999px;
}
.bell-item__body {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 3px;
  line-height: 1.5;
  white-space: pre-line;
}
.bell-item__time {
  font-size: 11px;
  color: var(--color-text-hint);
  margin-top: 5px;
}
.bell-dropdown__footer {
  padding: 10px 12px;
  border-top: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--bg-card) 90%, transparent);
}
.bell-dropdown__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(56, 124, 255, 0.14), rgba(83, 74, 183, 0.14));
  color: var(--color-purple);
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
}
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all .18s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
