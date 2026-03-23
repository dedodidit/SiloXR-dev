<script setup lang="ts">
const { $api } = useNuxtApp()
const router = useRouter()

type PendingTelegramLink = {
  link: string
  bot_user?: string
}

const pending = ref<PendingTelegramLink | null>(null)
const statusMessage = ref("We are waiting for Telegram to confirm your link.")
const loading = ref(true)
const checking = ref(false)
const linkOpened = ref(false)

let pollHandle: ReturnType<typeof setInterval> | null = null

const clearPendingLink = () => {
  if (!process.client) return
  sessionStorage.removeItem("siloxr-telegram-link")
}

const startPolling = () => {
  if (pollHandle) return
  pollHandle = setInterval(async () => {
    await refreshStatus(false)
  }, 3000)
}

const stopPolling = () => {
  if (!pollHandle) return
  clearInterval(pollHandle)
  pollHandle = null
}

const openTelegram = () => {
  if (!process.client || !pending.value?.link) return
  linkOpened.value = true
  window.open(pending.value.link, "_blank", "noopener,noreferrer")
  statusMessage.value = "Telegram opened. Send the bot start message there and we will continue automatically."
  startPolling()
}

const refreshStatus = async (showWorking = true) => {
  if (showWorking) checking.value = true
  try {
    const profile = await $api("/profile/")
    if (profile?.telegram_linked) {
      clearPendingLink()
      stopPolling()
      await router.replace("/dashboard")
      return
    }
  } catch {
    statusMessage.value = "We could not confirm Telegram yet. Try again in a moment."
  } finally {
    if (showWorking) checking.value = false
  }
}

const loadLink = async () => {
  loading.value = true
  try {
    await refreshStatus(false)
    if (process.client) {
      const raw = sessionStorage.getItem("siloxr-telegram-link")
      if (raw) {
        pending.value = JSON.parse(raw) as PendingTelegramLink
      }
    }
    if (!pending.value) {
      pending.value = await $api("/telegram/link/")
    }
    if (pending.value?.link) {
      openTelegram()
    }
  } catch {
    statusMessage.value = "We could not prepare Telegram linking right now. You can continue to the dashboard and finish it from account settings."
  } finally {
    loading.value = false
  }
}

onMounted(loadLink)
onBeforeUnmount(() => {
  stopPolling()
})

useHead({ title: "Complete Telegram setup - SiloXR" })
</script>

<template>
  <AuthShell
    eyebrow="One more step"
    title="Complete Telegram setup"
    subtitle="Finish Telegram linking now so SiloXR can use your chosen channel without asking you to repeat setup later."
    panel-title="Telegram handoff"
    panel-copy="We have already prepared your bot link. Open Telegram, send the start message once, and SiloXR will finish the connection automatically."
  >
    <div class="telegram-flow">
      <div class="telegram-card">
        <p class="telegram-card__title">What happens next</p>
        <p class="telegram-card__copy">
          1. Open the SiloXR bot.
          2. Send the prefilled start message.
          3. Return here. We will keep checking and move you into the dashboard as soon as the link is confirmed.
        </p>
      </div>

      <div class="telegram-actions">
        <button
          type="button"
          class="auth-btn"
          :disabled="loading || !pending?.link"
          @click="openTelegram"
        >
          {{ loading ? "Preparing Telegram..." : "Open Telegram bot" }}
        </button>

        <button
          type="button"
          class="auth-btn auth-btn--secondary"
          :disabled="checking"
          @click="refreshStatus()"
        >
          {{ checking ? "Checking link..." : "I have linked Telegram" }}
        </button>
      </div>

      <p class="telegram-status">{{ statusMessage }}</p>

      <p v-if="pending?.bot_user" class="telegram-meta">
        Bot: @{{ pending.bot_user }}
      </p>

      <div class="auth-links">
        <p class="auth-switch">
          Prefer to finish later?
          <NuxtLink to="/dashboard" class="auth-link" @click="clearPendingLink">Go to dashboard</NuxtLink>
        </p>
      </div>
    </div>
  </AuthShell>
</template>

<style scoped>
.telegram-flow {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.telegram-card {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--purple-bg) 72%, transparent), transparent 100%),
    var(--bg-raised);
}
.telegram-card__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.telegram-card__copy {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-2);
}
.telegram-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.telegram-status {
  font-size: 13px;
  color: var(--text-2);
}
.telegram-meta {
  font-size: 12px;
  color: var(--text-3);
}
.auth-btn {
  padding: 13px 14px;
  background: linear-gradient(135deg, var(--purple), var(--purple-2));
  color: #fff;
  border: none;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: transform .15s ease, box-shadow .15s ease, opacity .15s ease;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--purple) 28%, transparent);
}
.auth-btn--secondary {
  background: var(--bg-raised);
  color: var(--text);
  border: 1px solid var(--border);
  box-shadow: none;
}
.auth-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}
.auth-btn:disabled {
  opacity: .6;
  cursor: not-allowed;
}
.auth-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.auth-switch {
  font-size: 13px;
  color: var(--text-3);
}
.auth-link {
  color: var(--purple);
  font-weight: 600;
  text-decoration: none;
}
.auth-link:hover {
  text-decoration: underline;
}
</style>
