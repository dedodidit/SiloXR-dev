<script setup lang="ts">
import type { NotificationRecord, NotificationType } from "../../types"

const { $api } = useNuxtApp()

type NotificationFilter = "all" | "unread" | "inventory" | "activity"

const loading = ref(false)
const items = ref<NotificationRecord[]>([])
const activeFilter = ref<NotificationFilter>("all")

const typeLabel: Record<NotificationType, string> = {
  stockout_risk: "Stockout risk",
  dead_stock: "Dead stock",
  drop: "Demand drop",
  inactivity_risk: "Inactivity risk",
  generic: "Insight",
}

const typeFilter: Record<NotificationFilter, NotificationType[] | null> = {
  all: null,
  unread: null,
  inventory: ["stockout_risk", "dead_stock", "drop"],
  activity: ["inactivity_risk"],
}

const severityColor: Record<string, string> = {
  critical: "var(--severity-critical-text)",
  high: "var(--severity-warning-text)",
  medium: "var(--severity-info-text)",
  low: "var(--severity-ok-text)",
}

const severityTone: Record<string, string> = {
  critical: "notification-card--critical",
  high: "notification-card--high",
  medium: "notification-card--medium",
  low: "notification-card--low",
}

const channelLabel: Record<string, string> = {
  in_app: "In-app",
  email: "Email",
  whatsapp: "WhatsApp",
}

const load = async () => {
  loading.value = true
  try {
    items.value = await $api<NotificationRecord[]>("/notifications/")
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

const markAllRead = async () => {
  await $api("/notifications/read/", { method: "POST" })
  items.value = items.value.map((item) => ({ ...item, is_read: true }))
}

const refresh = async () => {
  await load()
}

const filteredItems = computed(() => {
  const byUnread = activeFilter.value === "unread"
    ? items.value.filter((item) => !item.is_read)
    : items.value

  const typeSet = typeFilter[activeFilter.value]
  if (!typeSet) return byUnread
  return byUnread.filter((item) => typeSet.includes(item.notification_type as NotificationType))
})

const unreadCount = computed(() => items.value.filter((item) => !item.is_read).length)
const criticalCount = computed(() => items.value.filter((item) => item.severity === "critical").length)
const inventoryCount = computed(() => items.value.filter((item) =>
  ["stockout_risk", "dead_stock", "drop"].includes(item.notification_type)
).length)
const activityCount = computed(() => items.value.filter((item) => item.notification_type === "inactivity_risk").length)

const filterTabs = computed(() => ([
  { key: "all" as const, label: "All", count: items.value.length },
  { key: "unread" as const, label: "Unread", count: unreadCount.value },
  { key: "inventory" as const, label: "Inventory", count: inventoryCount.value },
  { key: "activity" as const, label: "Activity", count: activityCount.value },
]))

const formatTime = (value: string) => new Date(value).toLocaleString()

const setFilter = (filter: NotificationFilter) => {
  activeFilter.value = filter
}

const goToDetail = (item: NotificationRecord) => {
  if (item.product_sku) return `/workspace/product-operations?product=${encodeURIComponent(item.product_sku)}`
  return "/dashboard"
}

useHead({ title: "Notifications - SiloXR" })

onMounted(load)
</script>

<template>
  <div class="page-pad notification-page">
    <div class="notification-page__hero surface">
      <div>
        <p class="notification-page__eyebrow">Notifications</p>
        <h1 class="t-heading">Actionable signals in one place</h1>
        <p class="t-body" style="margin-top:8px;max-width:720px">
          Inventory risks and inactivity warnings appear here first, so the next move stays obvious.
        </p>
      </div>

      <div class="notification-page__stats">
        <div class="notification-page__stat">
          <span>Unread</span>
          <strong>{{ unreadCount }}</strong>
        </div>
        <div class="notification-page__stat">
          <span>Critical</span>
          <strong>{{ criticalCount }}</strong>
        </div>
        <div class="notification-page__stat">
          <span>Insights</span>
          <strong>{{ items.length }}</strong>
        </div>
      </div>
    </div>

    <div class="notification-page__toolbar">
      <div class="notification-page__filters">
        <button
          v-for="tab in filterTabs"
          :key="tab.key"
          class="notification-page__filter"
          :class="{ 'notification-page__filter--active': activeFilter === tab.key }"
          @click="setFilter(tab.key)"
        >
          {{ tab.label }}
          <span>{{ tab.count }}</span>
        </button>
      </div>

      <div class="notification-page__actions">
        <button class="btn btn-secondary" :disabled="loading" @click="refresh">
          {{ loading ? "Refreshing..." : "Refresh" }}
        </button>
        <button class="btn btn-primary" :disabled="unreadCount === 0" @click="markAllRead">
          Mark all read
        </button>
      </div>
    </div>

    <div v-if="loading" class="notification-page__empty surface">
      Loading notifications...
    </div>

    <div v-else-if="!filteredItems.length" class="notification-page__empty surface">
      <h2>No matching notifications</h2>
      <p>Switch filters or wait for the next inventory or inactivity signal.</p>
      <NuxtLink to="/dashboard" class="btn btn-primary" style="margin-top:16px;width:fit-content">
        Back to dashboard
      </NuxtLink>
    </div>

    <div v-else class="notification-page__list">
      <article
        v-for="item in filteredItems"
        :key="item.id"
        class="notification-card surface"
        :class="[severityTone[item.severity] ?? 'notification-card--medium', { 'notification-card--unread': !item.is_read }]"
        :style="{ borderLeftColor: severityColor[item.severity] ?? 'var(--border)' }"
      >
        <div class="notification-card__top">
          <div class="notification-card__headline">
            <div class="notification-card__title-row">
              <h2 class="notification-card__title">{{ item.title }}</h2>
              <span class="notification-card__type">{{ typeLabel[item.notification_type] ?? "Insight" }}</span>
            </div>
            <p v-if="item.product_name" class="notification-card__product">{{ item.product_name }}</p>
          </div>
          <div class="notification-card__meta">
            <span class="notification-card__channel">{{ channelLabel[item.channel] ?? "In-app" }}</span>
            <span class="notification-card__time">{{ formatTime(item.created_at) }}</span>
          </div>
        </div>

        <p class="notification-card__body">{{ item.body }}</p>

        <div v-if="item.payload && Object.keys(item.payload).length" class="notification-card__payload">
          <span v-for="(value, key) in item.payload" :key="key" class="notification-card__pill">
            {{ key }}: {{ typeof value === "object" ? JSON.stringify(value) : value }}
          </span>
        </div>

        <div class="notification-card__footer">
          <NuxtLink :to="goToDetail(item)" class="notification-card__link">
            Open related view
          </NuxtLink>
          <span v-if="!item.is_read" class="notification-card__unread-dot">Unread</span>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.notification-page__hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding: 24px;
  margin-bottom: 18px;
}
.notification-page__eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-3);
}
.notification-page__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  min-width: 280px;
}
.notification-page__stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-sunken) 82%, transparent);
  border: 1px solid var(--border-subtle);
}
.notification-page__stat span {
  font-size: 11px;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: .05em;
}
.notification-page__stat strong {
  font-size: 22px;
  color: var(--text);
}
.notification-page__toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.notification-page__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.notification-page__filter {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.notification-page__filter span {
  min-width: 22px;
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--bg-sunken);
  font-size: 11px;
  text-align: center;
}
.notification-page__filter--active {
  background: linear-gradient(135deg, rgba(56, 124, 255, 0.12), rgba(83, 74, 183, 0.12));
  border-color: rgba(83, 74, 183, 0.22);
  color: var(--text);
}
.notification-page__actions {
  display: flex;
  gap: 10px;
}
.notification-page__empty {
  padding: 28px;
  text-align: center;
  color: var(--text-2);
}
.notification-page__empty h2 {
  font-size: 18px;
  margin-bottom: 6px;
}
.notification-page__list {
  display: grid;
  gap: 14px;
}
.notification-card {
  padding: 20px 22px;
  border-left: 4px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.notification-card--unread {
  box-shadow: 0 0 0 1px rgba(83, 74, 183, 0.08), var(--shadow-sm);
}
.notification-card--critical {
  background: linear-gradient(90deg, rgba(164, 45, 45, 0.08), transparent 40%);
}
.notification-card--high {
  background: linear-gradient(90deg, rgba(133, 79, 11, 0.08), transparent 40%);
}
.notification-card--medium {
  background: linear-gradient(90deg, rgba(83, 74, 183, 0.08), transparent 40%);
}
.notification-card--low {
  background: linear-gradient(90deg, rgba(59, 109, 17, 0.08), transparent 40%);
}
.notification-card__top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.notification-card__headline {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.notification-card__title-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.notification-card__title {
  font-size: 16px;
  line-height: 1.3;
  color: var(--text);
}
.notification-card__type {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(83, 74, 183, 0.1);
  color: var(--color-purple);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
}
.notification-card__product {
  font-size: 13px;
  color: var(--text-3);
}
.notification-card__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}
.notification-card__channel {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--color-purple);
  background: var(--color-purple-light, rgba(83, 74, 183, .1));
  padding: 4px 8px;
  border-radius: 999px;
}
.notification-card__time {
  font-size: 11px;
  color: var(--text-4);
}
.notification-card__body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-2);
}
.notification-card__payload {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.notification-card__pill {
  padding: 7px 10px;
  border-radius: 999px;
  background: var(--bg-sunken);
  font-size: 12px;
  color: var(--text-2);
}
.notification-card__footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.notification-card__link {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-purple);
  text-decoration: none;
}
.notification-card__link:hover {
  text-decoration: underline;
}
.notification-card__unread-dot {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(56, 124, 255, 0.1);
  color: var(--color-blue, #185FA5);
  font-size: 11px;
  font-weight: 700;
}

@media (max-width: 860px) {
  .notification-page__hero {
    flex-direction: column;
  }
  .notification-page__stats {
    width: 100%;
  }
  .notification-card__top,
  .notification-card__footer {
    flex-direction: column;
    align-items: flex-start;
  }
  .notification-card__meta {
    align-items: flex-start;
  }
}
</style>
