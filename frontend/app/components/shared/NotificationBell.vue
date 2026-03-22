<!-- frontend/app/components/shared/NotificationBell.vue -->

<script setup lang="ts">
const { $api }   = useNuxtApp()
const open       = ref(false)
const items      = ref<any[]>([])
const unreadCount = computed(() => items.value.filter(n => !n.is_read).length)

const load = async () => {
  try {
    items.value = await $api<any[]>("/notifications/")
  } catch { /* ignore */ }
}

const markRead = async () => {
  await $api("/notifications/read/", { method: "POST" })
  items.value = items.value.map(n => ({ ...n, is_read: true }))
}

const toggle = async () => {
  open.value = !open.value
  if (open.value) {
    await load()
    if (unreadCount.value > 0) await markRead()
  }
}

onMounted(() => {
  load()
  // Poll every 2 minutes
  const interval = setInterval(load, 2 * 60 * 1000)
  onUnmounted(() => clearInterval(interval))
})

const severityColor: Record<string, string> = {
  critical: "var(--severity-critical-text)",
  warning:  "var(--severity-warning-text)",
  info:     "var(--severity-info-text)",
  ok:       "var(--severity-ok-text)",
}

const channelLabel: Record<string, string> = {
  in_app: "In-app",
  email: "Email",
  telegram: "Telegram",
  whatsapp: "WhatsApp",
}
</script>

<template>
  <div class="bell-wrap">
    <button class="bell-btn" @click="toggle" :aria-label="`${unreadCount} notifications`">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M9 2a5 5 0 0 1 5 5v3l1.5 2H2.5L4 10V7a5 5 0 0 1 5-5Z"
          stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M7 14a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.4"/>
      </svg>
      <span v-if="unreadCount > 0" class="bell-badge">{{ unreadCount }}</span>
    </button>

    <Transition name="dropdown">
      <div v-if="open" class="bell-dropdown surface">
        <div class="bell-dropdown__header">
          <span>Notifications</span>
          <button class="bell-dropdown__close" @click="open = false">×</button>
        </div>
        <div class="bell-dropdown__list">
          <div v-if="!items.length" class="bell-dropdown__empty">
            No new notifications.
          </div>
          <div
            v-for="n in items" :key="n.id"
            class="bell-item"
            :style="{ borderLeftColor: severityColor[n.severity] ?? 'var(--color-border)' }"
          >
            <div class="bell-item__top">
              <div class="bell-item__title-wrap">
                <p class="bell-item__title">{{ n.title }}</p>
                <span v-if="n.product_name" class="bell-item__product">{{ n.product_name }}</span>
              </div>
              <span class="bell-item__channel">{{ channelLabel[n.channel] ?? 'In-app' }}</span>
            </div>
            <p class="bell-item__body">{{ n.body }}</p>
            <p class="bell-item__time">
              {{ new Date(n.created_at).toLocaleString() }}
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.bell-wrap{position:relative}
.bell-btn{background:none;border:none;cursor:pointer;color:var(--color-text-muted);position:relative;padding:6px;border-radius:var(--radius-sm);transition:color .15s}
.bell-btn:hover{color:var(--color-text)}
.bell-badge{position:absolute;top:0;right:0;width:16px;height:16px;border-radius:50%;background:var(--color-red);color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center}
.bell-dropdown{position:absolute;top:calc(100% + 8px);right:0;width:320px;z-index:200;display:flex;flex-direction:column;max-height:420px;overflow:hidden}
.bell-dropdown__header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--color-border);font-size:13px;font-weight:600;color:var(--color-text)}
.bell-dropdown__close{background:none;border:none;cursor:pointer;font-size:18px;color:var(--color-text-muted);line-height:1}
.bell-dropdown__list{overflow-y:auto;flex:1}
.bell-dropdown__empty{padding:24px;text-align:center;font-size:13px;color:var(--color-text-hint)}
.bell-item{padding:12px 16px;border-left:3px solid var(--color-border);border-bottom:1px solid var(--color-border)}
.bell-item__top{display:flex;align-items:center;justify-content:space-between;gap:10px}
.bell-item__title-wrap{display:flex;flex-direction:column;gap:3px;min-width:0}
.bell-item__title{font-size:13px;font-weight:600;color:var(--color-text)}
.bell-item__product{font-size:11px;color:var(--color-text-hint)}
.bell-item__channel{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--color-purple);background:var(--color-purple-light, rgba(83,74,183,.1));padding:3px 7px;border-radius:999px}
.bell-item__body{font-size:12px;color:var(--color-text-muted);margin-top:3px;line-height:1.5;white-space:pre-line}
.bell-item__time{font-size:11px;color:var(--color-text-hint);margin-top:5px}
.dropdown-enter-active,.dropdown-leave-active{transition:all .18s ease}
.dropdown-enter-from,.dropdown-leave-to{opacity:0;transform:translateY(-6px)}
</style>
